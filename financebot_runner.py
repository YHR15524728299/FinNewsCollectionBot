import argparse

import financebot


def parse_args():
    parser = argparse.ArgumentParser(description="Run FinNewsCollectionBot locally with Ollama.")
    parser.add_argument("--max-articles", type=int, default=5, help="max RSS entries per source")
    parser.add_argument("--no-push", action="store_true", help="do not push to ServerChan")
    return parser.parse_args()


def main():
    args = parse_args()

    print(f"LLM_BASE_URL={financebot.LLM_BASE_URL}")
    print("LLM_MODELS=" + ",".join(model["name"] for model in financebot.MODEL_POOL))

    report_path = financebot.run_bot(max_articles=args.max_articles, push=not args.no_push)
    print(f"报告已生成: {report_path}")


if __name__ == "__main__":
    main()
