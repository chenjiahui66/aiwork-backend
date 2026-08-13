"""
一键启动脚本 - 自动用 venv 的 python 跑 uvicorn

用法（在项目根 D:\\project\\MVPdemo\\aiwork-backend 下执行）:
    .venv\Scripts\python.exe run.py
    或
    py run.py

效果: 等价于 .venv\Scripts\python.exe -m uvicorn app.main:app --reload
"""
import os
import subprocess
import sys
from pathlib import Path


def find_venv_python() -> str:
    """Locate the venv Python executable."""
    root = Path(__file__).resolve().parent
    if sys.platform == "win32":
        candidates = [root / ".venv" / "Scripts" / "python.exe"]
    else:
        candidates = [root / ".venv" / "bin" / "python"]
    for p in candidates:
        if p.exists():
            return str(p)
    raise FileNotFoundError(
        ".venv not found. Please run:\n"
        "  python -m venv .venv\n"
        "  .venv\\Scripts\\python.exe -m pip install -r requirements.txt"
    )


def main() -> None:
    venv_py = find_venv_python()
    print(f"[run.py] Using venv: {venv_py}")

    # Load .env into os.environ so uvicorn child process sees it
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file)
            print("[run.py] Loaded .env")
        except ImportError:
            print("[run.py] (python-dotenv not installed; relying on raw env vars)")

    # Run uvicorn
    cmd = [
        venv_py,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        os.getenv("APP_HOST", "0.0.0.0"),
        "--port",
        os.getenv("APP_PORT", "8001"),
        "--reload",
    ]
    print(f"[run.py] Starting: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n[run.py] Stopped.")


if __name__ == "__main__":
    main()
