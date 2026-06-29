param(
    [string]$Model = $env:OLLAMA_MODEL,
    [int]$MaxArticles = 5,
    [switch]$NoPush
)

if (-not $env:OLLAMA_BASE_URL) {
    $env:OLLAMA_BASE_URL = "http://localhost:11434/v1"
}

$PythonExe = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

$ArgsList = @("local_launcher.py", "--max-articles", "$MaxArticles")
if ($Model) {
    $ArgsList += @("--model", $Model)
}
if ($NoPush) {
    $ArgsList += "--no-push"
}

& $PythonExe @ArgsList
