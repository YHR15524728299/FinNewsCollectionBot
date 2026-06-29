import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import financebot
from local_launcher import get_installed_ollama_models


DEFAULT_MODEL = "qwen2.5:7b"


class RunCancelled(Exception):
    pass


def prepare_model_options(installed_models, current_model):
    options = []
    for model in [*installed_models, current_model]:
        if model and model not in options:
            options.append(model)
    return options or [DEFAULT_MODEL]


def format_status_line(status, model, output_path=None, elapsed_seconds=None):
    parts = [f"状态：{status}", f"模型：{model}"]
    if elapsed_seconds is not None:
        minutes, seconds = divmod(max(0, int(elapsed_seconds)), 60)
        parts.append(f"用时：{minutes:02d}:{seconds:02d}")
    if output_path:
        parts.append(f"输出：{output_path}")
    return " | ".join(parts)


class FinNewsGui:
    def __init__(self, root):
        self.root = root
        self.root.title("FinNewsCollectionBot 本地运行器")
        self.root.geometry("1120x720")
        self.root.minsize(960, 620)

        self.queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker = None
        self.latest_report_path = None
        self.started_at = None
        self.current_status = "等待启动"
        self.current_model = DEFAULT_MODEL
        self.current_output_path = None

        self.base_url_var = tk.StringVar(value=os.getenv("OLLAMA_BASE_URL") or financebot.LLM_BASE_URL)
        self.model_var = tk.StringVar(value=os.getenv("OLLAMA_MODEL") or DEFAULT_MODEL)
        self.max_articles_var = tk.IntVar(value=5)
        self.push_var = tk.BooleanVar(value=False)
        self.server_keys_var = tk.StringVar(value=os.getenv("SERVER_CHAN_KEYS") or "")
        self.status_var = tk.StringVar(value=format_status_line("等待启动", self.model_var.get()))

        self._build_ui()
        self.refresh_models()
        self.root.after(100, self._drain_queue)
        self.root.after(1000, self._refresh_elapsed_status)

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        left = ttk.Frame(main, padding=12)
        right = ttk.Frame(main, padding=12)
        main.add(left, weight=0)
        main.add(right, weight=1)

        self._build_controls(left)
        self._build_output(right)

    def _build_controls(self, parent):
        parent.columnconfigure(0, weight=1)

        ttk.Label(parent, text="操作区", font=("Microsoft YaHei UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 14)
        )

        ttk.Label(parent, text="Ollama 地址").grid(row=1, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.base_url_var, width=34).grid(
            row=2, column=0, sticky="ew", pady=(4, 12)
        )

        ttk.Label(parent, text="模型").grid(row=3, column=0, sticky="w")
        model_row = ttk.Frame(parent)
        model_row.grid(row=4, column=0, sticky="ew", pady=(4, 12))
        model_row.columnconfigure(0, weight=1)
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var, width=22)
        self.model_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(model_row, text="刷新", command=self.refresh_models).grid(row=0, column=1, padx=(8, 0))

        ttk.Label(parent, text="每个来源最多文章数").grid(row=5, column=0, sticky="w")
        ttk.Spinbox(parent, from_=1, to=20, textvariable=self.max_articles_var, width=8).grid(
            row=6, column=0, sticky="w", pady=(4, 12)
        )

        ttk.Checkbutton(parent, text="推送到 Server 酱", variable=self.push_var).grid(
            row=7, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(parent, text="Server 酱 Key（可选，多个用逗号分隔）").grid(row=8, column=0, sticky="w")
        ttk.Entry(parent, textvariable=self.server_keys_var, width=34, show="*").grid(
            row=9, column=0, sticky="ew", pady=(4, 18)
        )

        button_row = ttk.Frame(parent)
        button_row.grid(row=10, column=0, sticky="ew")
        button_row.columnconfigure(0, weight=1)
        button_row.columnconfigure(1, weight=1)
        self.start_button = ttk.Button(button_row, text="开始生成", command=self.start_run)
        self.start_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.stop_button = ttk.Button(button_row, text="停止", command=self.stop_run, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.open_button = ttk.Button(parent, text="打开输出目录", command=self.open_output_dir)
        self.open_button.grid(row=11, column=0, sticky="ew", pady=(12, 0))

    def _build_output(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        parent.rowconfigure(5, weight=3)

        ttk.Label(parent, text="状态区", font=("Microsoft YaHei UI", 13, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(parent, textvariable=self.status_var).grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(parent, text="运行日志").grid(row=2, column=0, sticky="nw")
        self.log_text = tk.Text(parent, height=10, wrap="word")
        self.log_text.grid(row=3, column=0, sticky="nsew", pady=(4, 12))
        self.log_text.configure(state=tk.DISABLED)

        ttk.Label(parent, text="最终报告").grid(row=4, column=0, sticky="nw")
        self.report_text = tk.Text(parent, wrap="word")
        self.report_text.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        self.report_text.configure(state=tk.DISABLED)

    def refresh_models(self):
        models = prepare_model_options(get_installed_ollama_models(), self.model_var.get())
        self.model_combo["values"] = models
        if self.model_var.get() not in models:
            self.model_var.set(models[0])
        self._log(f"已刷新模型列表：{', '.join(models)}")

    def start_run(self):
        if self.worker and self.worker.is_alive():
            return

        model = self.model_var.get().strip()
        base_url = self.base_url_var.get().strip()
        if not model:
            messagebox.showerror("缺少模型", "请选择或输入 Ollama 模型名")
            return
        if not base_url:
            messagebox.showerror("缺少地址", "请填写 Ollama 地址")
            return

        try:
            max_articles = int(self.max_articles_var.get())
        except (TypeError, ValueError):
            messagebox.showerror("参数错误", "每个来源最多文章数必须是数字")
            return

        self.stop_event.clear()
        self.latest_report_path = None
        self.current_output_path = None
        self.started_at = time.monotonic()
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self._clear_report()
        self._set_status("准备启动", model)
        self._log(f"任务已启动：模型 {model}，每个来源最多 {max_articles} 条")

        self.worker = threading.Thread(
            target=self._run_worker,
            args=(base_url, model, max_articles, self.push_var.get(), self.server_keys_var.get()),
            daemon=True,
        )
        self.worker.start()

    def stop_run(self):
        self.stop_event.set()
        self._log("已请求停止，当前步骤结束后中断")

    def open_output_dir(self):
        output_dir = Path("outputs").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(output_dir)

    def _run_worker(self, base_url, model, max_articles, push, server_keys):
        try:
            financebot.configure_llm(base_url=base_url, api_key="ollama", models=[model])
            financebot.server_chan_keys = [item.strip() for item in server_keys.split(",") if item.strip()]

            report_path = financebot.run_bot(
                max_articles=max_articles,
                push=push,
                status_callback=lambda message: self._worker_status(message, model),
                log_callback=lambda message: self._queue_log(message),
            )
            report_text = Path(report_path).read_text(encoding="utf-8")
            self.queue.put(("report", str(report_path), report_text))
        except RunCancelled:
            self.queue.put(("cancelled",))
        except Exception as exc:
            self.queue.put(("error", str(exc)))
        finally:
            self.queue.put(("done",))

    def _worker_status(self, message, model):
        if self.stop_event.is_set():
            raise RunCancelled()
        self.queue.put(("status", message, model, None))

    def _queue_log(self, message):
        self.queue.put(("log", message))

    def _drain_queue(self):
        while True:
            try:
                event = self.queue.get_nowait()
            except queue.Empty:
                break

            event_type = event[0]
            if event_type == "status":
                _, status, model, output_path = event
                self._set_status(status, model, output_path)
            elif event_type == "log":
                self._log(event[1])
            elif event_type == "report":
                _, report_path, report_text = event
                self.latest_report_path = report_path
                self._set_status("完成", self.model_var.get(), report_path)
                self._set_report(report_text)
            elif event_type == "cancelled":
                self._set_status("已停止", self.model_var.get(), self.latest_report_path)
            elif event_type == "error":
                self._set_status("失败", self.model_var.get(), self.latest_report_path)
                self._log(f"运行失败：{event[1]}")
                messagebox.showerror("运行失败", event[1])
            elif event_type == "done":
                self.start_button.configure(state=tk.NORMAL)
                self.stop_button.configure(state=tk.DISABLED)

        self.root.after(100, self._drain_queue)

    def _set_status(self, status, model, output_path=None):
        self.current_status = status
        self.current_model = model
        if output_path:
            self.current_output_path = output_path

        elapsed_seconds = None
        if self.started_at is not None:
            elapsed_seconds = int(time.monotonic() - self.started_at)

        self.status_var.set(
            format_status_line(
                self.current_status,
                self.current_model,
                self.current_output_path,
                elapsed_seconds=elapsed_seconds,
            )
        )

    def _refresh_elapsed_status(self):
        if self.worker and self.worker.is_alive() and self.started_at is not None:
            self._set_status(self.current_status, self.current_model, self.current_output_path)
        self.root.after(1000, self._refresh_elapsed_status)

    def _log(self, message):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _clear_report(self):
        self.report_text.configure(state=tk.NORMAL)
        self.report_text.delete("1.0", tk.END)
        self.report_text.configure(state=tk.DISABLED)

    def _set_report(self, report):
        self.report_text.configure(state=tk.NORMAL)
        self.report_text.delete("1.0", tk.END)
        self.report_text.insert("1.0", report)
        self.report_text.configure(state=tk.DISABLED)


def main():
    root = tk.Tk()
    FinNewsGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()
