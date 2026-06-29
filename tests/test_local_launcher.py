import unittest

import local_launcher


class FakeCompletedProcess:
    def __init__(self, stdout="", returncode=0):
        self.stdout = stdout
        self.returncode = returncode


class LocalLauncherTest(unittest.TestCase):
    def test_parse_installed_ollama_models_from_ollama_list(self):
        output = """NAME               ID              SIZE      MODIFIED
qwen2.5:7b         abc123          4.7 GB    2 days ago
llama3.1:8b        def456          4.9 GB    1 week ago
"""

        models = local_launcher.parse_ollama_list(output)

        self.assertEqual(models, ["qwen2.5:7b", "llama3.1:8b"])

    def test_get_installed_models_returns_empty_when_ollama_fails(self):
        def fake_run(*args, **kwargs):
            return FakeCompletedProcess(returncode=1)

        self.assertEqual(local_launcher.get_installed_ollama_models(fake_run), [])

    def test_choose_model_defaults_to_first_installed_model(self):
        model = local_launcher.choose_model(
            ["qwen2.5:7b", "llama3.1:8b"],
            input_func=lambda prompt: "",
            print_func=lambda message: None,
        )

        self.assertEqual(model, "qwen2.5:7b")

    def test_choose_model_by_number(self):
        model = local_launcher.choose_model(
            ["qwen2.5:7b", "llama3.1:8b"],
            input_func=lambda prompt: "2",
            print_func=lambda message: None,
        )

        self.assertEqual(model, "llama3.1:8b")

    def test_choose_model_accepts_manual_model_name(self):
        answers = iter(["m", "deepseek-r1:8b"])

        model = local_launcher.choose_model(
            ["qwen2.5:7b"],
            input_func=lambda prompt: next(answers),
            print_func=lambda message: None,
        )

        self.assertEqual(model, "deepseek-r1:8b")


if __name__ == "__main__":
    unittest.main()
