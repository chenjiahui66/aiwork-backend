"""
pytest 配置 - 全局 fixture
"""
import sys
from pathlib import Path

# 让 pytest 能找到 app 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))