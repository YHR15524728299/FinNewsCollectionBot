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
    if any(d in domain for d in FORCE_RENDER_DOMAINS):
        use_render = True

    for attempt in range(1, retries + 1):
        try:
            print(f"📰 抓取第 {attempt} 次: {url}")
            resp = session.get(url, timeout=12, allow_redirects=True)
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}")

            body = resp.text or ""
            if len(body) < 300 and attempt < retries:
                raise Exception(f"页面内容过短（{len(body)}），疑似反爬或重定向壳")

            if "window.location" in body or "location.href" in body:
                match = re.search(r"location\.href\s*=\s*['\"](.*?)['\"]", body)
                if match:
                    redirected = match.group(1)
                    print(f"🔁 检测到JS跳转，尝试跳转至 {redirected}")
                    resp = session.get(redirected, timeout=12, allow_redirects=True)
                    body = resp.text or ""

            article = Article(url)
            article.set_html(body)
            article.parse()
            text = (article.text or "").strip()

            if len(text) > 200:
                print(f"✅ 抓取成功（{len(text)} 字）")
                return text[:3000]
            else:
                print(f"⚠️ 抓取到文本太短（{len(text)} 字），可能失败，重试...")

        except Exception as e:
            print(f"❌ 第 {attempt} 次失败: {e}")
            time.sleep(2 * attempt)

    if use_render and RENDER_AVAILABLE:
        try:
            print(f"⚙️ 尝试动态渲染: {url}")
            session_r = HTMLSession()
            r = session_r.get(url, timeout=20)
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


def fetch_feed_with_headers(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    return feedparser.parse(url, request_headers=headers)


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



def fetch_rss_articles(rss_feeds, max_per_source=5):
    news_data = {}
    analysis_text = ""
    stats = {"total": 0, "success": 0, "failed": 0}

    for category, sources 在 rss_feeds.items():
        category_content = ""
        for source, url 在 sources.items():
            print(f"📡 正在获取 {source} 的 RSS 源: {url}")
            feed = fetch_feed_with_retry(url)
            if not feed:
                print(f"⚠️ 无法获取 {source} 的 RSS 数据")
                continue
            print(f"✅ {source} RSS 获取成功，共 {len(feed.entries)} 条新闻")

            articles = []
            for entry 在 feed.entries[:max_per_source]:
                stats['total'] += 1
                title = entry.get('title'， '无标题')
                link = entry.get('link'， '') or entry.get('guid', '')
                if not link:
                    print(f"⚠️ {source} 的新闻 '{title}' 没有链接，跳过")
                    stats['failed'] += 1
                    text = fetch_article_text(link)
                if text == "（抓取失败）":
                    stats['failed'] += 1
                else:
                    stats['success'] += 1

                article_summary = f"【{source}】{title}\n{link}\n{text}\n\n"
                category_content += article_summary
                analysis_text += article_summary

        if category_content:
            news_data[category] = category_content

    print(f"📊 抓取统计: 总 {stats['total']}，成功 {stats['success']}，失败 {stats['failed']}")
    return news_data, analysis_text


def summarize(text):
    completion = openai_client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": """
你是一名专业的财经新闻分析师，请根据以下新闻内容生成1500字以内摘要：
1. 提取主要行业/主题，找出近1天涨幅最高的3个行业，以及近3天涨幅较高且此前2周表现平淡的3个行业。
2. 针对每个热点，输出催化剂、复盘、展望。
3. 摘要逻辑清晰，重点突出，适合专业投资者。
"""},
            {"role": "user", "content": text}
        ]
    )
    return completion.choices[0].message.content.strip()

def send_to_wechat(title, content):
    for key in SERVER_CHAN_KEYS:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = {"title": title, "desp": content}
        response = requests.post(url, data=data, timeout=10)
        if response.ok:
            print(f"✅ 推送成功: {key}")
        else:
            print(f"❌ 推送失败: {key}, 响应：{response.text}")

if __name__ == "__main__":
    today_str = today_date().strftime("%Y-%m-%d")
    articles_data, analysis_text, stats = fetch_rss_articles(rss_feeds, max_per_source=5)
    summary = summarize(analysis_text)
    final_summary = f"📅 **{today_str} 财经新闻摘要**\n✍️ **今日分析总结：**\n{summary}\n\n---\n\n"
    for category, content in articles_data.items():
        if content.strip():
            final_summary += f"## {category}\n{content}\n\n"
    send_to_wechat(title=f"📌 {today_str} 财经新闻摘要", content=final_summary)
