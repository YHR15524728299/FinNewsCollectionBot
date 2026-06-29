# 福生无量天尊
from openai import OpenAI
import feedparser
import requests
from newspaper import Article, Config
from datetime import datetime
import time
import pytz
import os
from pathlib import Path


def _env(name, default=None):
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _env_list(*names, default=None):
    for name in names:
        value = _env(name)
        if value:
            return [item.strip() for item in value.split(",") if item.strip()]
    return default or []


# 本地默认使用 Ollama 的 OpenAI compatible endpoint。
LLM_BASE_URL = _env("LLM_BASE_URL") or _env("OLLAMA_BASE_URL") or "http://localhost:11434/v1"
LLM_API_KEY = _env("LLM_API_KEY") or _env("OLLAMA_API_KEY") or _env("ZHIPU_API_KEY") or "ollama"
LLM_MODELS = _env_list("LLM_MODELS", "OLLAMA_MODEL", "LLM_MODEL", default=["qwen2.5:7b"])

# Server酱可选；不配置时只生成本地报告，不推送微信。
server_chan_keys = _env_list("SERVER_CHAN_KEYS")

openai_client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)

# =========================
# LLM Router：本地可用 OLLAMA_MODEL/LLM_MODELS 指定一个或多个模型，失败自动切换
# =========================
MODEL_POOL = [{"name": model_name} for model_name in LLM_MODELS]

LLM_TIMEOUT_SECONDS = 120
ARTICLE_TIMEOUT_SECONDS = 8
RSS_TIMEOUT_SECONDS = 12


def _notify(callback, message):
    if callback:
        callback(message)


def configure_llm(base_url=None, api_key=None, models=None):
    global LLM_BASE_URL, LLM_API_KEY, LLM_MODELS, MODEL_POOL, openai_client

    if base_url:
        LLM_BASE_URL = base_url
    if api_key:
        LLM_API_KEY = api_key
    if models:
        LLM_MODELS = [model.strip() for model in models if model.strip()]
        MODEL_POOL = [{"name": model_name} for model_name in LLM_MODELS]

    openai_client = OpenAI(
        api_key=LLM_API_KEY,
        base_url=LLM_BASE_URL,
    )


def sort_models():
    if not all(model_item.get("expiry") for model_item in MODEL_POOL):
        return MODEL_POOL

    return sorted(
        MODEL_POOL,
        key=lambda x: datetime.strptime(x["expiry"], "%Y-%m-%d"),
        reverse=True
    )


def call_llm(messages, log_callback=None):
    last_error = None

    for model_item in sort_models():
        model_name = model_item["name"]
        try:
            print(f"🧠 使用模型: {model_name}")
            _notify(log_callback, f"Ollama 生成中：{model_name}，本地模型可能需要等待")
            completion = openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                timeout=LLM_TIMEOUT_SECONDS
            )
            _notify(log_callback, f"Ollama 生成完成：{model_name}")
            return (completion.choices[0].message.content or "").strip()
        except Exception as e:
            print(f"❌ 模型失败 {model_name} -> {e}")
            _notify(log_callback, f"模型失败：{model_name} -> {e}")
            last_error = e
            continue

    raise Exception(f"所有模型均失败: {last_error}")


rss_feeds = {
    "💲 华尔街见闻":{
        "华尔街见闻":"https://dedicated.wallstreetcn.com/rss.xml",      
    },
    "💻 36氪":{
        "36kr":"https://36kr.com/feed",   
    },
    "🇨🇳 中国经济": {
        "香港經濟日報":"https://www.hket.com/rss/china",
        "东方财富":"http://rss.eastmoney.com/rss_partener.xml",
        "国家统计局-最新发布":"https://www.stats.gov.cn/sj/zxfb/rss.xml",
    },
    "🇺🇸 美国经济": {
        "华尔街日报 - 经济":"https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",
        "华尔街日报 - 市场":"https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
        "MarketWatch美股": "https://www.marketwatch.com/rss/topstories",
        "ZeroHedge华尔街新闻": "https://feeds.feedburner.com/zerohedge/feed",
        "ETF Trends": "https://www.etftrends.com/feed/",
    },
    "🌍 世界经济": {
        "华尔街日报 - 经济":"https://feeds.content.dowjones.io/public/rss/socialeconomyfeed",
        "BBC全球经济": "http://feeds.bbci.co.uk/news/business/rss.xml",
    },
}

def today_date():
    return datetime.now(pytz.timezone("Asia/Shanghai")).date()

def fetch_article_text(url):
    try:
        config = Config()
        config.request_timeout = ARTICLE_TIMEOUT_SECONDS
        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.text[:800] if article.text else "（未能获取正文）"
    except:
        return "（未能获取正文）"

def fetch_feed_with_headers(url):
    headers = {'User-Agent':'Mozilla/5.0'}
    response = requests.get(url, headers=headers, timeout=RSS_TIMEOUT_SECONDS)
    response.raise_for_status()
    return feedparser.parse(response.content)

def fetch_feed_with_retry(url, retries=3, delay=5):
    for i in range(retries):
        try:
            feed = fetch_feed_with_headers(url)
            if feed and len(feed.entries) > 0:
                return feed
        except:
            time.sleep(delay)
    return None

def fetch_rss_articles(rss_feeds, max_articles=10, log_callback=None):
    news_data = {}
    analysis_text = ""

    for category, sources in rss_feeds.items():
        category_content = ""
        for source, url in sources.items():
            _notify(log_callback, f"抓取来源：{category} / {source}")
            feed = fetch_feed_with_retry(url)
            if not feed:
                _notify(log_callback, f"来源跳过：{source}，RSS 无返回")
                continue

            articles = []
            entries = feed.entries[:max_articles]
            for index, entry in enumerate(entries, start=1):
                title = entry.get('title','无标题')
                link = entry.get('link','') or entry.get('guid','')
                if not link:
                    _notify(log_callback, f"跳过无链接文章：{title}")
                    continue

                _notify(log_callback, f"读取文章 {index}/{len(entries)}：{title}")
                text = fetch_article_text(link)
                analysis_text += f"【{title}】\n{text}\n\n"

                articles.append(f"- [{title}]({link})")

            if articles:
                category_content += f"### {source}\n" + "\n".join(articles) + "\n\n"
                _notify(log_callback, f"来源完成：{source}，收录 {len(articles)} 条")
            else:
                _notify(log_callback, f"来源完成：{source}，未收录文章")

        news_data[category] = category_content

    return news_data, analysis_text


def summarize(text, log_callback=None):
    return call_llm([
        {"role": "system", "content": """你是顶级券商分析师，专为专业投资者服务。请根据新闻内容完成以下分析：

## 一、市场情绪
一句话概括当前市场状态（30字内）

## 二、热点行业/主题分析
找出近1日涨幅最高的3个行业或主题，以及近3天涨幅较高且此前2周表现平淡的3个行业/主题。（如新闻未提供具体涨幅，请结合描述和市场情绪推测）

针对每个热点，按以下结构分析：

### 热点名称
- **催化剂：** 触发上涨的原因（政策、数据、事件、情绪等）
- **复盘：** 梳理过去1个月该行业/主题的核心逻辑、关键动态与阶段性走势
- **展望：** 判断该热点是短期炒作还是有持续行情潜力

## 三、关键新闻速览
5-8条重要新闻，每条一句话要点

## 四、未来一周的重要事件预告
找出未来一周的关键重点时间预告，每条1-2句话描述

## 五、策略建议
明日操作建议（2-3句话）

【原则】
- 逻辑清晰、重点突出
- 数据+逻辑+结论
- 用emoji增强可读性
- 全文控制在1500字以内"""},
        {"role": "user", "content": text}
    ], log_callback=log_callback)


def send_to_wechat(title, content):
    if not server_chan_keys:
        print("未配置 SERVER_CHAN_KEYS，跳过微信推送")
        return

    for key in server_chan_keys:
        url = f"https://sctapi.ftqq.com/{key}.send"
        requests.post(url, data={"title":title,"desp":content}, timeout=10)


def build_report(max_articles=5, status_callback=None, log_callback=None):
    today_str = today_date().strftime("%Y-%m-%d")
    _notify(status_callback, "抓取 RSS")
    _notify(log_callback, f"开始抓取 RSS，每个来源最多 {max_articles} 条")
    articles_data, analysis_text = fetch_rss_articles(
        rss_feeds,
        max_articles=max_articles,
        log_callback=log_callback,
    )

    _notify(status_callback, "调用 Ollama")
    _notify(log_callback, "开始调用本地 LLM 生成摘要")
    summary = summarize(analysis_text, log_callback=log_callback)

    final_summary = f"📅 {today_str} 财经速览\n\n{summary}\n\n---\n\n📰 重点新闻\n"

    for category, content in articles_data.items():
        if content.strip():
            final_summary += f"{category}\n{content}\n"

    return today_str, final_summary


def save_report(content, output_dir="outputs"):
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    file_path = output_path / f"finance-news-{today_date().strftime('%Y-%m-%d')}.md"
    file_path.write_text(content, encoding="utf-8")
    return file_path


def run_bot(max_articles=5, push=True, output_dir="outputs", status_callback=None, log_callback=None):
    today_str, final_summary = build_report(
        max_articles=max_articles,
        status_callback=status_callback,
        log_callback=log_callback,
    )

    _notify(status_callback, "保存报告")
    _notify(log_callback, "正在保存 Markdown 报告")
    report_path = save_report(final_summary, output_dir=output_dir)

    if push:
        _notify(status_callback, "推送微信")
        _notify(log_callback, "正在推送到 Server 酱")
        send_to_wechat(f"{today_str} 财经速览", final_summary)

    _notify(status_callback, "完成")
    _notify(log_callback, f"报告已生成: {report_path}")
    return report_path


if __name__ == "__main__":
    run_bot()
    print("DONE")
