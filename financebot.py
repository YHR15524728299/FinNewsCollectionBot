# financebot_high_success.py
# 智能化高成功率财经新闻抓取、AI 摘要（Deepseek）与 ServerChan 推送
# 适用于 GitHub Actions / 本地运行。复制替换原 financebot.py 即可。

from openai import OpenAI
import feedparser
import requests
from newspaper import Article
from datetime import datetime
import time
import pytz
import os
import random
import re
from urllib.parse import urlparse

# 可选动态渲染依赖（如果未安装，脚本仍能工作但无法渲染JS页面）
try:
    from requests_html import HTMLSession
    RENDER_AVAILABLE = True
except Exception:
    RENDER_AVAILABLE = False

# 配置（环境变量）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVER_CHAN_KEYS_ENV = os.getenv("SERVER_CHAN_KEYS")
if not SERVER_CHAN_KEYS_ENV:
    raise ValueError("环境变量 SERVER_CHAN_KEYS 未设置，请在 GitHub Actions 中设置此变量！")
SERVER_CHAN_KEYS = [k.strip() for k in SERVER_CHAN_KEYS_ENV.split(",") if k.strip()]

if not OPENAI_API_KEY:
    raise ValueError("环境变量 OPENAI_API_KEY 未设置！")

# Deepseek OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.deepseek.com/v1")
DEEPSEEK_MODEL = "deepseek-chat"

# RSS源（按需增删）
rss_feeds = {
    "💲 华尔街见闻": {"华尔街见闻": "https://dedicated.wallstreetcn.com/rss.xml"},
    "💻 36氪": {"36氪": "https://36kr.com/feed"},
    "🇨🇳 中国经济": {
        "香港經濟日報": "https://www.hket.com/rss/china",
        "东方财富": "http://rss.eastmoney.com/rss_partener.xml",
        "百度股票焦点": "http://news.baidu.com/n?cmd=1&class=stock&tn=rss&sub=0",
        "中新网": "https://www.chinanews.com.cn/rss/finance.xml",
        "国家统计局-最新发布": "https://www.stats.gov.cn/sj/zxfb/rss.xml",
    },
    "🇺🇸 美国经济": {
        "华尔街日报 - 经济": "https://feeds.content.dowjones.io/public/rss/WSJcomUSBusiness",
        "华尔街日报 - 市场": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
        "MarketWatch美股": "https://www.marketwatch.com/rss/topstories",
        "ZeroHedge华尔街新闻": "https://feeds.feedburner.com/zerohedge/feed",
        "ETF Trends": "https://www.etftrends.com/feed/",
    },
    "🌍 世界经济": {
        "华尔街日报 - 经济": "https://feeds.content.dowjones.io/public/rss/socialeconomyfeed",
        "BBC全球经济": "http://feeds.bbci.co.uk/news/business/rss.xml",
    },
}

# 域名强制渲染策略（遇到这些域名优先使用 render）
FORCE_RENDER_DOMAINS = [
    "wallstreetcn.com",
    "36kr.com",
    "bloomberg.com",
    "wsj.com",
    "bbc.com",
]

# 获取北京时间
def today_date():
    return datetime.now(pytz.timezone("Asia/Shanghai")).date()

# 智能抓取正文函数（高成功率版）
def fetch_article_text(url, retries=3, use_render=True):
    """
    优先使用 requests + newspaper 提取正文。
    失败后可选使用 requests_html 的渲染作为 fallback（如果已安装）。
    返回：抓取到的纯文本（字符串），或特定失败占位字符串。
    """

    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.1 Safari/537.36",
    ]

    headers = {
        "User-Agent": random.choice(ua_list),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    session = requests.Session()
    session.headers.update(headers)

    domain = urlparse(url).netloc or ""
    # 如果域名命中强制渲染列表，启用 render
    if any(d in domain for d in FORCE_RENDER_DOMAINS):
        use_render = True

    for attempt in range(1, retries + 1):
        try:
            print(f"📰 抓取第 {attempt} 次: {url}")
            resp = session.get(url, timeout=12, allow_redirects=True)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")

            # 简单反爬检测：页面过短或包含 anti-bot 标识
            body = resp.text or ""
            if len(body) < 300 and attempt < retries:
                raise Exception(f"页面内容过短（{len(body)}），疑似反爬或重定向壳")

            # 检测 JS 重定向
            if "window.location" in body or "location.href" in body:
                match = re.search(r"location\.href\s*=\s*['\"](.*?)['\"]", body)
                if match:
                    redirected = match.group(1)
                    print(f"🔁 检测到JS跳转，尝试跳转至 {redirected}")
                    resp = session.get(redirected, timeout=12, allow_redirects=True)
                    body = resp.text or ""

            # 使用 newspaper 提取正文
            article = Article(url)
            article.set_html(body)
            article.parse()
            text = (article.text or "").strip()

            if len(text) > 200:
                # 成功
                print(f"✅ 抓取成功（{len(text)} 字）")
                return text[:3000]
            else:
                # 可能解析失败，重试
                print(f"⚠️ 抓取到文本太短（{len(text)} 字），可能失败，重试...")

        except Exception as e:
            print(f"❌ 第 {attempt} 次失败: {e}")
            time.sleep(2 * attempt)

    # 渲染 fallback（只在可用时启用）
    if use_render and RENDER_AVAILABLE:
        try:
            print(f"⚙️ 尝试动态渲染: {url}")
            session_r = HTMLSession()
            r = session_r.get(url, timeout=20)
            # render 可能消耗显著时间，请根据需要调整 timeout/sleep
            r.html.render(timeout=30, sleep=2)
            paragraphs = [p.text for p in r.html.find('p') if len(p.text) > 40]
            text = "\n".join(paragraphs)
            if len(text) > 200:
                print(f"✅ 动态渲染成功（{len(text)} 字）")
                return text[:3000]
            else:
                print(f"⚠️ 渲染后正文仍然过短（{len(text)} 字）")
        except Exception as e:
            print(f"❌ 动态渲染失败: {e}")

    print(f"🚫 最终抓取失败: {url}")
    return "（抓取失败）"


# 添加 User-Agent 头获取 RSS
def fetch_feed_with_headers(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    return feedparser.parse(url, request_headers=headers)


# 自动重试获取 RSS
def fetch_feed_with_retry(url, retries=3, delay=5):
    for i in range(retries):
        try:
            feed = fetch_feed_with_headers(url)
            if feed and hasattr(feed, 'entries') and len(feed.entries) > 0:
                return feed
            else:
                print(f"⚠️ RSS 返回但无 entries: {url}")
        except Exception as e:
            print(f"⚠️ 第 {i+1} 次请求 {url} 失败: {e}")
        time.sleep(delay)
    print(f"❌ 跳过 {url}, 尝试 {retries} 次后仍失败。")
    return None


# 获取RSS并爬正文（用于AI分析）
def fetch_rss_articles(rss_feeds, max_per_source=5):
    news_data = {}
    analysis_text = ""
    stats = {"total": 0, "success": 0, "failed": 0}

    for category, sources in rss_feeds.items():
        category_content = ""
        for source, url in sources.items():
            print(f"📡 正在获取 {source} 的 RSS 源: {url}")
            feed = fetch_feed_with_retry(url)
            if not feed:
                print(f"⚠️ 无法获取 {source} 的 RSS 数据")
                continue
            print(f"✅ {source} RSS 获取成功，共 {len(feed.entries)} 条新闻")

            articles = []
            for entry in feed.entries[:max_per_source]:
                stats['total'] += 1
                title = entry.get('title', '无标题')
                link = entry.get('link', '') or entry.get('guid', '')
                if not link:
                    print(f"⚠️ {source} 的新闻 '{title}' 没有链接，跳过")
                    stats['failed'] += 1
                    continue

                article_text = fetch_article_text(link, retries=3, use_render=False)
                if article_text and not article_text.startswith('（抓取失败'):
                    stats['success'] += 1
                    analysis_text += f"【{title}】\n{article_text}\n\n"
                    print(f"🔹 {source} - {title} 获取成功")
                else:
                    stats['failed'] += 1
                    print(f"🔸 {source} - {title} 抓取失败")

                articles.append(f"- [{title}]({link})")

            if articles:
                category_content += f"### {source}\n" + "\n".join(articles) + "\n\n"

        news_data[category] = category_content

    print(f"📊 抓取统计: 总计 {stats['total']} 篇，成功 {stats['success']} 篇，失败 {stats['failed']} 篇")
    return news_data, analysis_text, stats


# AI 生成内容摘要（基于爬取的正文）
def summarize(text):
    completion = openai_client.chat.completions。create(
        model="deepseek-chat"，
        messages=[
            {"role": "system", "content": """
             你是一名专业的财经新闻分析师，请根据以下新闻内容，按照以下步骤完成任务：
             1. 提取新闻中涉及的主要行业和主题，找出近1天涨幅最高的3个行业或主题，以及近3天涨幅较高且此前2周表现平淡的3个行业/主题。（如新闻未提供具体涨幅，请结合描述和市场情绪推测热点）
             2. 针对每个热点，输出：
                - 催化剂：分析近期上涨的可能原因（政策、数据、事件、情绪等）。
                - 复盘：梳理过去3个月该行业/主题的核心逻辑、关键动态与阶段性走势。
                - 展望：判断该热点是短期炒作还是有持续行情潜力。
             3. 将以上分析整合为一篇1500字以内的财经热点摘要，逻辑清晰、重点突出，适合专业投资者阅读。
             """}，
            {"role": "user", "content": text}
        ]
    )
    return completion.choices[0].message.content.strip()

# 发送微信推送
def send_to_wechat(title, content):
    for key 在 server_chan_keys:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = {"title": title, "desp": content}
        response = requests.post(url, data=data, timeout=10)
        if response.ok:
            print(f"✅ 推送成功: {key}")
        else:
            print(f"❌ 推送失败: {key}, 响应：{response.text}")


if __name__ == "__main__":
    today_str = today_date().strftime("%Y-%m-%d")

    # 每个网站获取最多 5 篇文章
    articles_data, analysis_text = fetch_rss_articles(rss_feeds, max_articles=5)
    
    # AI生成摘要
    summary = summarize(analysis_text)

    # 生成仅展示标题和链接的最终消息
    final_summary = f"📅 **{today_str} 财经新闻摘要**\n\✍️ **今日分析总结：**\n{summary}\n\n---\n\n"
    for category, content 在 articles_data.items():
        if content.strip():
            final_summary += f"## {category}\n{content}\n\n"

    # 推送到多个server酱key
    send_to_wechat(title=f"📌 {today_str} 财经新闻摘要", content=final_summary)
