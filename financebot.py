# 福生无量天尊
from openai import OpenAI
import feedparser
import requests
from newspaper import Article
from datetime import datetime
import time
import pytz
import os

# API Key（统一使用 GitHub Secrets: ZHIPU_API_KEY）
api_key = os.getenv("ZHIPU_API_KEY")
if not api_key:
    raise ValueError("环境变量 ZHIPU_API_KEY 未设置，请在Github Actions中配置")

# Server酱
server_chan_keys_env = os.getenv("SERVER_CHAN_KEYS")
if not server_chan_keys_env:
    raise ValueError("环境变量 SERVER_CHAN_KEYS 未设置")
server_chan_keys = server_chan_keys_env.split(",")

# 阿里云百炼 OpenAI compatible endpoint
openai_client = OpenAI(
    api_key=api_key,
    base_url="https://llm-eklvu5yxpltr5j2l.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
)

# =========================
# LLM Router：按免费额度到期时间排序，失败自动切换
# =========================
MODEL_POOL = [
    {"name": "glm-5.2", "expiry": "2026-09-15"},
    {"name": "qwen3.7-max-preview", "expiry": "2026-08-24"},
    {"name": "deepseek-v4-flash", "expiry": "2026-07-24"},
    {"name": "kimi-k2.6", "expiry": "2026-07-21"},
]

LLM_TIMEOUT_SECONDS = 120


def sort_models():
    return sorted(
        MODEL_POOL,
        key=lambda x: datetime.strptime(x["expiry"], "%Y-%m-%d"),
        reverse=True
    )


def call_llm(messages):
    last_error = None

    for model_item in sort_models():
        model_name = model_item["name"]
        try:
            print(f"🧠 使用模型: {model_name}")
            completion = openai_client.chat.completions.create(
                model=model_name,
                messages=messages,
                timeout=LLM_TIMEOUT_SECONDS
            )
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ 模型失败 {model_name} -> {e}")
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
        article = Article(url)
        article.download()
        article.parse()
        return article.text[:800] if article.text else "（未能获取正文）"
    except:
        return "（未能获取正文）"

def fetch_feed_with_headers(url):
    headers = {'User-Agent':'Mozilla/5.0'}
    return feedparser.parse(url, request_headers=headers)

def fetch_feed_with_retry(url, retries=3, delay=5):
    for i in range(retries):
        try:
            feed = fetch_feed_with_headers(url)
            if feed and len(feed.entries) > 0:
                return feed
        except:
            time.sleep(delay)
    return None

def fetch_rss_articles(rss_feeds, max_articles=10):
    news_data = {}
    analysis_text = ""

    for category, sources in rss_feeds.items():
        category_content = ""
        for source, url in sources.items():
            feed = fetch_feed_with_retry(url)
            if not feed:
                continue

            articles = []
            for entry in feed.entries[:5]:
                title = entry.get('title','无标题')
                link = entry.get('link','') or entry.get('guid','')
                if not link:
                    continue

                text = fetch_article_text(link)
                analysis_text += f"【{title}】\n{text}\n\n"

                articles.append(f"- [{title}]({link})")

            if articles:
                category_content += f"### {source}\n" + "\n".join(articles) + "\n\n"

        news_data[category] = category_content

    return news_data, analysis_text


def summarize(text):
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
    ])


def send_to_wechat(title, content):
    for key in server_chan_keys:
        url = f"https://sctapi.ftqq.com/{key}.send"
        requests.post(url, data={"title":title,"desp":content}, timeout=10)


if __name__ == "__main__":
    today_str = today_date().strftime("%Y-%m-%d")
    articles_data, analysis_text = fetch_rss_articles(rss_feeds, max_articles=5)
    summary = summarize(analysis_text)

    final_summary = f"📅 {today_str} 财经速览\n\n{summary}\n\n---\n\n📰 重点新闻\n"

    for category, content in articles_data.items():
        if content.strip():
            final_summary += f"{category}\n{content}\n"

    send_to_wechat(f"{today_str} 财经速览", final_summary)
    print("DONE")