if (-not $env:OLLAMA_BASE_URL) {
    $env:OLLAMA_BASE_URL = "http://localhost:11434/v1"
}

$PythonExe = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

& $PythonExe local_gui.py
