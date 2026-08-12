#!/usr/bin/env python3
"""今日选股数据发布器

用法:
  python publish.py             # 自动 commit + push（使用 .env 里的 token）
  python publish.py --dry-run   # 只生成 commit，不 push

流程:
  1. 读 today.json
  2. git add data/
  3. git commit -m "data: update today.json for YYYY-MM-DD"
  4. git push origin main
  5. GitHub Pages 自动更新
"""
import sys
import os
import json
import subprocess
from datetime import datetime

REPO_DIR = r"C:\Users\Administrator\AppData\Local\hermes\projects\h5-trading"
DATA_DIR = os.path.join(REPO_DIR, "data")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
ENV_PATH = r"C:\Users\Administrator\AppData\Local\hermes\.env"


def get_github_token():
    """从 .env 读 token（绝对不打印到 stdout）"""
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("GITHUB_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise FileNotFoundError(f"GITHUB_TOKEN not in {ENV_PATH}")


def run(cmd, cwd=None, env=None, check=True):
    """Run shell command with proper error handling"""
    result = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        shell=True,
        encoding="utf-8"
    )
    if check and result.returncode != 0:
        print(f"❌ cmd failed: {cmd}")
        print(f"   stdout: {result.stdout}")
        print(f"   stderr: {result.stderr}")
        raise RuntimeError(f"Command failed: {cmd[0]}")
    return result


def publish(dry_run=False):
    """git commit + push today.json"""
    # 0. 检查 today.json 存在
    if not os.path.exists(TODAY_PATH):
        print(f"❌ today.json 不存在: {TODAY_PATH}")
        print("   先跑: python build_today.py --demo")
        return False

    with open(TODAY_PATH, "r", encoding="utf-8") as f:
        today_data = json.load(f)
    today = today_data.get("date", "unknown")

    print(f"=== 发布今日选股 ===")
    print(f"  日期: {today}")
    print(f"  标的数: {len(today_data.get('stocks', []))}")
    print(f"  仓库: {REPO_DIR}")
    print(f"  模式: {'dry-run (不push)' if dry_run else 'commit + push'}")
    print()

    # 1. git config（用 token 推）
    token = get_github_token()

    # 设置 remote URL（带 token）
    remote_url = f"https://x-access-token:{token}@github.com/liken00/h5-trading.git"

    # 2. git add data/
    print("→ git add data/")
    result = run(["git", "add", "data/"], cwd=REPO_DIR)
    print(result.stdout.strip() if result.stdout else "")

    # 3. git status（确认有变更）
    print("\n→ git status")
    result = run(["git", "status", "--short"], cwd=REPO_DIR, check=False)
    if not result.stdout.strip():
        print("  (无变更)")
        return True
    print(result.stdout)

    # 4. git commit
    msg = f"data: update today.json for {today}"
    print(f"\n→ git commit -m \"{msg}\"")
    result = run(["git", "commit", "-m", msg], cwd=REPO_DIR, check=False)
    if "nothing to commit" in (result.stdout + result.stderr):
        print("  (无新 commit)")
    else:
        print(result.stdout.strip() if result.stdout else "")

    if dry_run:
        print("\n[dry-run] 不 push")
        return True

    # 5. git push（带 token）
    print(f"\n→ git push origin main")
    env = os.environ.copy()
    env["GIT_ASKPASS"] = "echo"
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = run(["git", "push", remote_url, "main"], cwd=REPO_DIR, env=env)
    print(result.stdout.strip() if result.stdout else "")
    if result.stderr:
        print(f"  stderr: {result.stderr.strip()}")

    print("\n✅ 已推送到 GitHub")
    print(f"   GitHub Pages: https://liken00.github.io/h5-trading/")
    print(f"   触发时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("   （Pages 通常 30 秒 - 2 分钟内更新）")
    return True


def main():
    dry_run = "--dry-run" in sys.argv
    publish(dry_run=dry_run)


if __name__ == "__main__":
    main()