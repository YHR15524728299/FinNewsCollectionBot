# FinNewsCollectionBot 本地版

本项目在本地抓取财经 RSS，调用本机 Ollama LLM 生成财经速览，并保存为 Markdown 文件。Server 酱推送为可选项。

## 运行入口

推荐窗口入口：

```powershell
.\start_gui.ps1
```

窗口里可以选择 Ollama 模型、设置最大文章数、查看运行状态、运行日志和最终报告。

命令行入口：

```powershell
.\start_local.ps1 -NoPush
```

启动后会读取 `ollama list`，显示本机已安装模型，输入编号即可启动。

直接指定模型：

```powershell
.\start_local.ps1 -Model qwen2.5:7b -NoPush
```

等价 Python 入口：

```powershell
.\.venv\Scripts\python.exe local_launcher.py --no-push
```

跳过选择器并指定模型：

```powershell
.\.venv\Scripts\python.exe local_launcher.py --model qwen2.5:7b --no-push
```

输出文件：

```text
outputs/finance-news-YYYY-MM-DD.md
```

## 本地准备

1. 安装并启动 Ollama。

2. 拉取默认模型：

```powershell
ollama pull qwen2.5:7b
```

3. 创建 Python 虚拟环境并安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. 启动本地任务：

窗口版：

```powershell
.\start_gui.ps1
```

命令行版：

```powershell
.\start_local.ps1 -NoPush
```

选择界面示例：

```text
可用 Ollama 模型:
1. qwen2.5:7b
2. llama3.1:8b
m. 手动输入模型名
选择模型 [1-2，默认 1]:
```

## 可配置项

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Ollama OpenAI compatible endpoint |
| `OLLAMA_MODEL` | `qwen2.5:7b` | 本地模型名 |
| `LLM_MODELS` | 空 | 多模型逗号分隔，失败时按顺序切换 |
| `SERVER_CHAN_KEYS` | 空 | 可选，配置后推送到 Server 酱 |

## 窗口版说明

窗口左侧是操作区：

- `Ollama 地址`：默认 `http://localhost:11434/v1`
- `模型`：自动读取 `ollama list`，也可以手动输入模型名
- `每个来源最多文章数`：控制每个 RSS 来源抓取数量
- `推送到 Server 酱`：默认关闭

窗口右侧是输出区：

- `状态区`：显示当前步骤和输出文件
- `运行日志`：显示抓取、分析、保存等过程
- `最终报告`：任务完成后显示完整 Markdown 正文

示例：

```powershell
$env:OLLAMA_MODEL="qwen2.5:14b"
$env:OLLAMA_BASE_URL="http://localhost:11434/v1"
.\start_local.ps1 -NoPush
```

也可以不设置环境变量，直接传参：

```powershell
.\start_local.ps1 -Model qwen2.5:14b -NoPush
```

## 微信推送

不配置 `SERVER_CHAN_KEYS` 时，任务只生成本地 Markdown，不推送微信。

需要推送时：

```powershell
$env:SERVER_CHAN_KEYS="your_serverchan_key"
.\start_local.ps1
```

多个 key 用英文逗号分隔。

## 当前流程

1. 抓取 RSS 新闻源。
2. 提取正文片段。
3. 调用本地 Ollama 模型生成财经速览。
4. 保存到 `outputs/`。
5. 如配置 `SERVER_CHAN_KEYS`，同步推送到微信。
