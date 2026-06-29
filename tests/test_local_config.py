import importlib
import os
import sys
import unittest
from unittest import mock


def import_financebot_without_env():
    sys.modules.pop("financebot", None)
    with mock.patch.dict(
        os.environ,
        {
            "ZHIPU_API_KEY": "",
            "SERVER_CHAN_KEYS": "",
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
            "LLM_MODELS": "",
            "OLLAMA_BASE_URL": "",
            "OLLAMA_API_KEY": "",
            "OLLAMA_MODEL": "",
        },
        clear=False,
    ):
        return importlib.import_module("financebot")


class LocalConfigTest(unittest.TestCase):
    def test_import_uses_local_ollama_without_cloud_api_key(self):
        financebot = import_financebot_without_env()

        self.assertEqual(financebot.LLM_BASE_URL, "http://localhost:11434/v1")
        self.assertEqual(financebot.MODEL_POOL, [{"name": "qwen2.5:7b"}])

    def test_send_to_wechat_is_skipped_without_server_chan_keys(self):
        financebot = import_financebot_without_env()

        with mock.patch.object(financebot.requests, "post") as post:
            financebot.send_to_wechat("title", "content")

        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
