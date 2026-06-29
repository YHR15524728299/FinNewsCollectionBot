import tempfile
import unittest
from pathlib import Path
from unittest import mock

import financebot
import local_gui


class GuiRunnerTest(unittest.TestCase):
    def test_run_bot_emits_readable_statuses_and_writes_report(self):
        statuses = []
        logs = []

        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                financebot,
                "fetch_rss_articles",
                return_value=({"市场": "### 来源\n- [标题](https://example.com)\n"}, "新闻正文"),
            ), mock.patch.object(financebot, "summarize", return_value="本地摘要"), mock.patch.object(
                financebot, "send_to_wechat"
            ) as send_to_wechat:
                report_path = financebot.run_bot(
                    max_articles=2,
                    push=False,
                    output_dir=temp_dir,
                    status_callback=statuses.append,
                    log_callback=logs.append,
                )

            content = Path(report_path).read_text(encoding="utf-8")

        self.assertEqual(statuses, ["抓取 RSS", "调用 Ollama", "保存报告", "完成"])
        self.assertTrue(any("开始抓取 RSS" in item for item in logs))
        self.assertIn("本地摘要", content)
        send_to_wechat.assert_not_called()

    def test_prepare_model_options_keeps_current_model_visible(self):
        options = local_gui.prepare_model_options(["qwen2.5:7b", "llama3.1:8b"], "deepseek-r1:8b")

        self.assertEqual(options, ["qwen2.5:7b", "llama3.1:8b", "deepseek-r1:8b"])

    def test_format_status_line_includes_output_path(self):
        line = local_gui.format_status_line("完成", "qwen2.5:7b", "outputs/report.md")

        self.assertEqual(line, "状态：完成 | 模型：qwen2.5:7b | 输出：outputs/report.md")

    def test_format_status_line_can_show_elapsed_time(self):
        line = local_gui.format_status_line("抓取 RSS", "qwen2.5:7b", elapsed_seconds=65)

        self.assertEqual(line, "状态：抓取 RSS | 模型：qwen2.5:7b | 用时：01:05")

    def test_fetch_rss_articles_emits_source_and_article_logs(self):
        class FakeFeed:
            entries = [
                {"title": "第一条新闻", "link": "https://example.com/1"},
                {"title": "第二条新闻", "link": "https://example.com/2"},
            ]

        logs = []

        with mock.patch.object(financebot, "fetch_feed_with_retry", return_value=FakeFeed()), mock.patch.object(
            financebot, "fetch_article_text", return_value="正文"
        ):
            financebot.fetch_rss_articles(
                {"市场": {"来源A": "https://example.com/rss"}},
                max_articles=2,
                log_callback=logs.append,
            )

        self.assertIn("抓取来源：市场 / 来源A", logs)
        self.assertIn("读取文章 1/2：第一条新闻", logs)
        self.assertIn("读取文章 2/2：第二条新闻", logs)
        self.assertIn("来源完成：来源A，收录 2 条", logs)


if __name__ == "__main__":
    unittest.main()
