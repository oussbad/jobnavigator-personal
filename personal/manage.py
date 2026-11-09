#!/usr/bin/env python3
"""Host-native JobNavigator: private PostgreSQL, API, Codex runner and dashboard."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".personal"
PYTHON = ROOT / ".venv313/bin/python"

def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)

def settings():
    STATE.mkdir(mode=0o700, exist_ok=True)
    STATE.chmod(0o700)
    path = STATE / "settings.json"
    if not path.exists():
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump({"dashboard_key": secrets.token_urlsafe(32),
                       "db_password": secrets.token_urlsafe(32)}, f)
    return json.loads(path.read_text())

def environment():
    cfg = settings()
    env = dict(os.environ)
    if cfg.get("codex_use_user_config"):
        env.setdefault("JN_CODEX_USE_USER_CONFIG", "1")
    env.update(DATABASE_URL="postgresql://jobnavigator:" + cfg["db_password"] +
               "@127.0.0.1:55432/jobnavigator", INITIAL_API_KEY=cfg["dashboard_key"],
               JN_TELEMETRY="off", JN_SKIP_DEMO_RESUME="1", JN_SCHEDULER_DISABLED="1", JN_RUNNER_MANAGEMENT="0",
               JN_RUNNER_TOKEN_FILE=str(STATE / "runner-token"),
               JN_CODEX_RUNNER_URL="http://127.0.0.1:8011", JN_RUNNER_PROVIDER="codex_cli")
    return env

def alive(name):
    f = STATE / (name + ".pid")
    if not f.exists():
        return None
    try:
        pid = int(f.read_text())
        command = subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True)
        # Refuse stale/reused PIDs belonging to anything outside this checkout.
        return pid if str(ROOT) in command else None
    except (ValueError, subprocess.CalledProcessError):
        return None

def free(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            raise SystemExit(f"Port {port} is occupied; no existing service was stopped.")

def launch(name, args, env):
    if alive(name):
        return
    with (STATE / (name + ".log")).open("ab") as log:
        proc = subprocess.Popen([str(x) for x in args], cwd=ROOT, env=env,
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    (STATE / (name + ".pid")).write_text(str(proc.pid))

def wait_http(url, name):
    for _ in range(90):
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, TimeoutError):
            pass
        if not alive(name):
            break
        time.sleep(0.5)
    raise SystemExit(f"{name} did not start. Check .personal/{name}.log locally.")

def start():
    if not PYTHON.exists():
        raise SystemExit("Run bash personal/install.sh first.")
    node = shutil.which("node")
    if not node:
        raise SystemExit("Node.js is required; load your nvm environment first.")
    if not (ROOT / "frontend/node_modules/vite/bin/vite.js").exists():
        raise SystemExit("Run bash personal/install.sh first (frontend dependencies missing).")
    env = environment()
    pgdata = STATE / "postgres"
    if not pgdata.exists():
        pw = STATE / "pg-password"
        pw.write_text(settings()["db_password"])
        pw.chmod(0o600)
        try:
            run(["initdb", "-D", pgdata, "-U", "jobnavigator", "--auth=scram-sha-256",
                 "--pwfile", pw], stdout=subprocess.DEVNULL)
        finally:
            pw.unlink(missing_ok=True)
    running = subprocess.run(["pg_ctl", "-D", str(pgdata), "status"], capture_output=True).returncode == 0
    if not running:
        free(55432)
        run(["pg_ctl", "-D", pgdata, "-l", STATE / "postgres.log", "-o",
             "-h 127.0.0.1 -p 55432 -k " + str(STATE), "-w", "start"], stdout=subprocess.DEVNULL)
    pgenv = dict(env, PGPASSWORD=settings()["db_password"])
    found = subprocess.check_output(["psql", "-h", "127.0.0.1", "-p", "55432", "-U",
                                    "jobnavigator", "-d", "postgres", "-Atc",
                                    "SELECT 1 FROM pg_database WHERE datname='jobnavigator'"], env=pgenv, text=True)
    if found.strip() != "1":
        run(["createdb", "-h", "127.0.0.1", "-p", "55432", "-U", "jobnavigator", "jobnavigator"], env=pgenv)
    for name, port in (("api", 8000), ("runner", 8011), ("dashboard", 5173)):
        if not alive(name):
            free(port)
    launch("api", [PYTHON, "-m", "uvicorn", "backend.main:app", "--app-dir", ROOT, "--host", "127.0.0.1", "--port", "8000"], env)
    wait_http("http://127.0.0.1:8000/health", "api")
    launch("runner", [PYTHON, "-m", "uvicorn", "backend.cli_runner.server:app", "--app-dir", ROOT, "--host", "127.0.0.1", "--port", "8011"], env)
    wait_http("http://127.0.0.1:8011/health", "runner")
    launch("dashboard", [node, ROOT / "frontend/node_modules/vite/bin/vite.js", str(ROOT / "frontend"),
                         "--host", "127.0.0.1", "--port", "5173", "--strictPort"], env)
    wait_http("http://127.0.0.1:5173", "dashboard")
    print("Ready: http://127.0.0.1:5173 — scheduler and telemetry are off.")
    print("Dashboard key is in .personal/settings.json (local only).")

def stop():
    for name in ("dashboard", "runner", "api"):
        pid = alive(name)
        if pid:
            os.killpg(pid, signal.SIGTERM)
        (STATE / (name + ".pid")).unlink(missing_ok=True)
    pgdata = STATE / "postgres"
    if pgdata.exists():
        subprocess.run(["pg_ctl", "-D", str(pgdata), "-m", "fast", "-w", "stop"], capture_output=True)
    print("Stopped this checkout's services; data preserved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "status"])
    args = parser.parse_args()
    if args.action == "start":
        start()
    elif args.action == "stop":
        stop()
    else:
        for name in ("api", "runner", "dashboard"):
            print(name, "running" if alive(name) else "stopped")
