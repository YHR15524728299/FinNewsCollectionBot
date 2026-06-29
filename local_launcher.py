import argparse
import os
import subprocess
import sys


def parse_ollama_list(output):
    models = []
    for line in output.splitlines():
        parts = line.split()
        if not parts or parts[0].upper() == "NAME":
            continue
        models.append(parts[0])
    return models


def get_installed_ollama_models(run_func=subprocess.run):
    try:
        result = run_func(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return []

    if result.returncode != 0:
        return []
    return parse_ollama_list(result.stdout)


def choose_model(models, input_func=input, print_func=print):
    if not models:
        return input_func("未读取到已安装模型，请输入 Ollama 模型名: ").strip() or "qwen2.5:7b"

    print_func("可用 Ollama 模型:")
    for index, model in enumerate(models, start=1):
        print_func(f"{index}. {model}")
    print_func("m. 手动输入模型名")

    while True:
        answer = input_func(f"选择模型 [1-{len(models)}，默认 1]: ").strip()
        if not answer:
            return models[0]
        if answer.lower() == "m":
            manual_model = input_func("输入模型名: ").strip()
            if manual_model:
                return manual_model
            print_func("模型名不能为空")
            continue
        if answer.isdigit():
            selected_index = int(answer)
            if 1 <= selected_index <= len(models):
                return models[selected_index - 1]
        print_func("输入无效，请重新选择")


def parse_args():
    parser = argparse.ArgumentParser(description="Select an Ollama model and run the local bot.")
    parser.add_argument("--max-articles", type=int, default=5, help="max RSS entries per source")
    parser.add_argument("--no-push", action="store_true", help="do not push to ServerChan")
    parser.add_argument("--model", help="skip selector and use this model")
    return parser.parse_args()


def main():
    args = parse_args()
    model = args.model or choose_model(get_installed_ollama_models())

    env = os.environ.copy()
    env["OLLAMA_MODEL"] = model
    env.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")

    command = [
        sys.executable,
        "financebot_runner.py",
        "--max-articles",
        str(args.max_articles),
    ]
    if args.no_push:
        command.append("--no-push")

    print(f"使用模型: {model}")
    return subprocess.run(command, env=env).returncode


if __name__ == "__main__":
    raise SystemExit(main())
