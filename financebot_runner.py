import financebot

financebot.MODEL_POOL = [
    {"name": "glm-5.2", "expiry": "2026-09-15"},
    {"name": "qwen3.5-ocr", "expiry": "2026-09-14"},
    {"name": "qwen3.7-max-preview", "expiry": "2026-08-24"},
    {"name": "deepseek-v4-flash", "expiry": "2026-07-24"},
    {"name": "qwen3.5-plus-2026-04-20", "expiry": "2026-07-23"},
    {"name": "qwen3.6-27b", "expiry": "2026-07-23"},
    {"name": "kimi-k2.6", "expiry": "2026-07-21"},
    {"name": "qwen3.6-max-preview", "expiry": "2026-07-20"},
    {"name": "qwen3.6-flash-2026-04-16", "expiry": "2026-07-17"},
    {"name": "qwen3.6-35b-a3b", "expiry": "2026-07-17"},
    {"name": "qwen3.6-flash", "expiry": "2026-07-17"},
    {"name": "glm-5.1", "expiry": "2026-07-14"},
    {"name": "qwen3.6-plus-2026-04-02", "expiry": "2026-07-02"},
    {"name": "qwen3.6-plus", "expiry": "2026-07-02"},
]

if __name__ == "__main__":
    today_str = financebot.today_date().strftime("%Y-%m-%d")
    articles_data, analysis_text = financebot.fetch_rss_articles(financebot.rss_feeds, max_articles=5)
    summary = financebot.summarize(analysis_text)

    final_summary = f"📅 {today_str} 财经速览\n\n{summary}\n\n---\n\n📰 重点新闻\n"

    for category, content in articles_data.items():
        if content.strip():
            final_summary += f"{category}\n{content}\n"

    financebot.send_to_wechat(f"{today_str} 财经速览", final_summary)
    print("DONE")
