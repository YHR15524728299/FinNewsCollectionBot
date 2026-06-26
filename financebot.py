# 福生无量天尊
from openai import OpenAI
import feedparser
import requests
from newspaper import Article
from datetime import datetime
import time
import pytz
import os

# API Key（DashScope）
api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI")
if not api_key:
    raise ValueError("环境变量 DASHSCOPE_API_KEY 未设置，请在Github Actions中配置")

# Server酱
server_chan_keys_env = os.getenv("SERVER_CHAN_KEYS")
if not server_chan_keys_env:
    raise ValueError("环境变量 SERVER_CHAN_KEYS 未设置")
server_chan_keys = server_chan_keys_env.split(",")

# DashScope OpenAI compatible
openai_client = OpenAI(
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

MODEL_NAME = "qwen3.7-max"

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
    completion = openai_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role":"system","content":"你是顶级券商分析师"},
            {"role":"user","content":text}
        ]
    )
    return completion.choices[0].message.content.strip()

def send_to_wechat(title, content):
    for key in server_chan_keys:
        url = f"https://sctapi.ftqq.com/{key}.send"
        requests.post(url, data={"title":title,"desp":content}, timeout=10)

if __name__ == "__main__":
    today_str = today_date().strftime("%Y-%m-%d")
    _, analysis_text = fetch_rss_articles(rss_feeds, max_articles=5)
    summary = summarize(analysis_text)

    final = f"📅 {today_str} 财经速览\n\n{summary}\n"

    send_to_wechat(f"{today_str} 财经速览", final)
    print("DONE")