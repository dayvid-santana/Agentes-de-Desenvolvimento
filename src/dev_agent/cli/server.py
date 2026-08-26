"""Controle do servidor local com PID para Windows."""
from __future__ import annotations
import os
import subprocess
import sys
import time
from pathlib import Path
import httpx

PORT = 8765
URL = f"http://127.0.0.1:{PORT}"

def state_path() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "DevAgent" / "server.pid"
def running() -> bool:
    try: return httpx.get(f"{URL}/health", timeout=0.5).status_code == 200
    except httpx.HTTPError: return False
def start() -> bool:
    if running(): return False
    path = state_path(); path.parent.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen([sys.executable, "-m", "dev_agent.api.app"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    path.write_text(str(process.pid), encoding="utf-8")
    for _ in range(25):
        if running(): return True
        time.sleep(0.2)
    return False
def stop() -> bool:
    path = state_path()
    if not path.exists(): return False
    try:
        pid = int(path.read_text(encoding="utf-8")); subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
    finally: path.unlink(missing_ok=True)
    return True
