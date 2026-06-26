# 福生无量天尊
from openai import OpenAI
import feedparser
import requests
from newspaper import Article
from datetime import datetime
import time
import pytz
import os

# 获取 API Key（GLM / OpenAI 兼容接口）
api_key = os.getenv("ZHIPU_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI")
if not api_key:
    raise ValueError("环境变量 ZHIPU_API_KEY 未设置，请在Github Actions中设置此变量！")

# 从环境变量获取 Server酱 SendKeys
server_chan_keys_env = os.getenv("SERVER_CHAN_KEYS")
if not server_chan_keys_env:
    raise ValueError("环境变量 SERVER_CHAN_KEYS 未设置，请在Github Actions中设置此变量！")
server_chan_keys = server_chan_keys_env.split(",")

# 使用 GLM OpenAI 兼容接口
openai_client = OpenAI(
    api_key=api_key,
    base_url="https://open.bigmodel.cn/api/paas/v4",
)

MODEL_NAME = "glm-5.2"

# RSS源地址列表
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
        print(f"📰 正在爬取文章内容: {url}")
        article = Article(url)
        article.download()
        article.parse()
        text = article.text[:800]
        if not text:
            print(f"⚠️ 文章内容为空: {url}")
        return text
    except Exception as e:
        print(f"❌ 文章爬取失败: {url}，错误: {e}")
        return "（未能获取文章正文）"

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
            print(f"⚠️ 第 {i+1} 次请求 {url} 失败: {e}")
            time.sleep(delay)
    print(f"❌ 跳过 {url}, 尝试 {retries} 次后仍失败。")
    return None

def fetch_rss_articles(rss_feeds, max_articles=10):
    news_data = {}
    analysis_text = ""

    for category, sources in rss_feeds.items():
        category_content = ""
        for source, url in sources.items():
            print(f"📡 正在获取 {source} 的 RSS 源: {url}")
            feed = fetch_feed_with_retry(url)
            if not feed:
                continue

            articles = []
            for entry in feed.entries[:5]:
                title = entry.get('title', '无标题')
                link = entry.get('link', '') or entry.get('guid', '')
                if not link:
                    continue

                article_text = fetch_article_text(link)
                analysis_text += f"【{title}】\n{article_text}\n\n"

                articles.append(f"- [{title}]({link})")

            if articles:
                category_content += f"### {source}\n" + "\n".join(articles) + "\n\n"

        news_data[category] = category_content

    return news_data, analysis_text

def summarize(text):
    completion = openai_client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "你是顶级券商分析师，输出结构化金融分析"},
            {"role": "user", "content": text}
        ]
    )
    return completion.choices[0].message.content.strip()

def send_to_wechat(title, content):
    for key in server_chan_keys:
        url = f"https://sctapi.ftqq.com/{key}.send"
        requests.post(url, data={"title": title, "desp": content}, timeout=10)

if __name__ == "__main__":
    today_str = today_date().strftime("%Y-%m-%d")
    articles_data, analysis_text = fetch_rss_articles(rss_feeds, max_articles=5)
    summary = summarize(analysis_text)

    final_summary = f"📅 {today_str} 财经速览\n\n{summary}\n\n"

    for category, content in articles_data.items():
        if content.strip():
            final_summary += f"{category}\n{content}\n"

    send_to_wechat(f"{today_str} 财经速览", final_summary)
    print("DONE")