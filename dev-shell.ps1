# PowerShell helper - 让 python/pip 在当前 shell 里指向 .venv
#
# 用法（在 aiwork-backend 目录下执行，注意前面有一个点表示"导入到当前 shell"）:
#     . .\dev-shell.ps1
#
# 之后 'python' / 'pip' 自动指 .venv 里的版本，不必再 Activate.ps1

$ErrorActionPreference = "Stop"

$script:VenvRoot = Join-Path $PSScriptRoot ".venv"
if (-not (Test-Path $script:VenvRoot)) {
    Write-Host "[dev-shell] .venv 不存在，请先：python -m venv .venv" -ForegroundColor Red
    return
}

$scriptsDir = Join-Path $script:VenvRoot "Scripts"
if (Test-Path $scriptsDir) {
    $env:PATH = "$scriptsDir;$env:PATH"
    $env:VIRTUAL_ENV = $script:VenvRoot
    $env:PYTHONHOME = ""
}

# 重新定义 python/pip 函数，强制走 venv
function python {
    & "$script:VenvRoot\Scripts\python.exe" @args
}
function pip {
    & "$script:VenvRoot\Scripts\python.exe" "-m" "pip" @args
}
function py {
    & "$script:VenvRoot\Scripts\python.exe" @args
}

Write-Host "[dev-shell] 已锁定 python/pip 到 $scriptsDir\python.exe" -ForegroundColor Green
Write-Host "[dev-shell] 验证：python -c \"import sys; print(sys.executable)\"" -ForegroundColor Cyan
