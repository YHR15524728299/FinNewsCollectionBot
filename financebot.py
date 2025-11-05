# financebot_final.py
# ✅ 最终版：DeepSeek 摘要 + RSS 抓取 + ServerChan 推送（限制链接≤30条）

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

# =============================
# 环境配置
# =============================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVER_CHAN_KEYS_ENV = os.getenv("SERVER_CHAN_KEYS")

if not OPENAI_API_KEY:
    raise ValueError("❌ 环境变量 OPENAI_API_KEY 未设置！")
if not SERVER_CHAN_KEYS_ENV:
    raise ValueError("❌ 环境变量 SERVER_CHAN_KEYS 未设置！")

SERVER_CHAN_KEYS = [k.strip() for k in SERVER_CHAN_KEYS_ENV.split(",") if k.strip()]

# DeepSeek Client
openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url="https://api.deepseek.com/v1")
DEEPSEEK_MODEL = "deepseek-chat"

# =============================
# RSS 源（保持不改动）
# =============================
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

# =============================
# 工具函数
# =============================
def today_date():
    return datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")

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
        except Exception as e:
            print(f"⚠️ 第 {i+1} 次获取 {url} 失败: {e}")
        time.sleep(delay)
    return None

# =============================
# 抓取 RSS 并提取链接
# =============================
def fetch_rss_articles(rss_feeds, max_per_source=5):
    links = []
    for category, sources in rss_feeds.items():
        for source, url in sources.items():
            feed = fetch_feed_with_retry(url)
            if not feed:
                continue
            for entry in feed.entries[:max_per_source]:
                link = entry.get("link", "")
                if link and link.startswith("http"):
                    links.append(link)
    return links

# =============================
# DeepSeek 摘要（保持你原版不改）
# =============================
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

# =============================
# ServerChan 推送
# =============================
def send_to_wechat(title, content):
    for key in SERVER_CHAN_KEYS:
        url = f"https://sctapi.ftqq.com/{key}.send"
        data = {"title": title, "desp": content}
        resp = requests.post(url, data=data, timeout=10)
        if resp.ok:
            print(f"✅ 推送成功: {key}")
        else:
            print(f"❌ 推送失败: {key}, {resp.text}")

# =============================
# 主流程
# =============================
if __name__ == "__main__":
    today_str = today_date()
    print("🚀 正在抓取 RSS 新闻 ...")
    links = fetch_rss_articles(rss_feeds)
    print(f"✅ 抓取完成，共 {len(links)} 条")

    # 限制最多 30 条链接
    links = links[:30]
    joined_links = "\n".join([f"- {url}" for url in links])

    print("🧠 正在生成 DeepSeek 摘要 ...")
    summary = summarize("\n".join(links))

    final_summary = f"""📅 **{today_str} 财经新闻摘要**

✍️ **AI 摘要：**
{summary}

---

📎 **新闻链接（共{len(links)}条）：**
{joined_links}
"""

    # 控制方糖推送字数（约 2000 字安全）
    if len(final_summary) > 2000:
        final_summary = final_summary[:1900] + "\n\n...（内容过长，部分已省略）"

    print("📤 正在推送至 ServerChan ...")
    send_to_wechat(f"📌 {today_str} 财经新闻摘要", final_summary)
    print("✅ 完成！")
