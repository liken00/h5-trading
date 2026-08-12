#!/usr/bin/env python3
"""收盘复盘脚本

用法:
  python review.py 600519 1735    # 给单只收盘价
  python review.py --batch         # 读 today.json，提示逐个输入收盘价

复盘内容:
  - 记录到 history.jsonl
  - 算胜率
  - 生成 history_summary.json
"""
import os
import sys
import json
import argparse
from datetime import datetime

DATA_DIR = r"C:\Users\Administrator\AppData\Local\hermes\projects\h5-trading\data"
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.jsonl")
SUMMARY_PATH = os.path.join(DATA_DIR, "history_summary.json")


def load_today():
    if not os.path.exists(TODAY_PATH):
        return None
    with open(TODAY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_history(records):
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def calc_result(entry, close):
    """算盈亏百分比 + win/loss"""
    if entry <= 0 or close <= 0:
        return None, None
    pct = (close - entry) / entry * 100
    result = "win" if pct > 0 else ("loss" if pct < 0 else "flat")
    return round(pct, 2), result


def review_one(date, code, name, entry, close, note=""):
    """单只复盘"""
    pct, result = calc_result(entry, close)
    return {
        "date": date,
        "code": code,
        "name": name,
        "entry": entry,
        "close": close,
        "pct": pct,
        "result": result,
        "note": note,
    }


def calc_summary(records):
    """算累计胜率"""
    if not records:
        return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0, "avg_pct": 0}
    wins = sum(1 for r in records if r.get("result") == "win")
    losses = sum(1 for r in records if r.get("result") == "loss")
    total = len(records)
    pcts = [r["pct"] for r in records if r.get("pct") is not None]
    avg = round(sum(pcts) / len(pcts), 2) if pcts else 0
    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "flats": total - wins - losses,
        "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
        "avg_pct": avg,
        "best": max(pcts) if pcts else None,
        "worst": min(pcts) if pcts else None,
        "as_of": datetime.now().strftime("%Y-%m-%d %H:%M")
    }


def main():
    parser = argparse.ArgumentParser(description="收盘复盘")
    parser.add_argument("code", nargs="?", help="股票代码")
    parser.add_argument("close", nargs="?", type=float, help="收盘价")
    parser.add_argument("--note", default="", help="备注")
    parser.add_argument("--batch", action="store_true", help="逐个输入今日 5 只")
    args = parser.parse_args()

    history = load_history()
    today = load_today()
    if not today:
        print("❌ today.json 不存在，先跑 build_today.py")
        return

    if args.batch:
        # 交互式：逐个问收盘价
        print(f"=== 今日 {today['date']} 复盘（逐只输入收盘价）===\n")
        new_records = []
        for s in today.get("stocks", []):
            code = s.get("code", "")
            name = s.get("name", "")
            entry = s.get("entry_price", 0)
            print(f"📊 {name}（{code}）入价 {entry}")
            while True:
                try:
                    close_input = input(f"  收盘价（直接回车跳过）: ").strip()
                    if not close_input:
                        break
                    close = float(close_input)
                    rec = review_one(today["date"], code, name, entry, close)
                    new_records.append(rec)
                    print(f"  ✅ {rec['pct']:+.2f}% [{rec['result']}]")
                    break
                except ValueError:
                    print("  请输入数字")
        if new_records:
            history.extend(new_records)
            save_history(history)
            print(f"\n✅ 已追加 {len(new_records)} 条到 history.jsonl")

    elif args.code and args.close is not None:
        # 单只
        s = next((x for x in today.get("stocks", []) if x.get("code") == args.code), None)
        if not s:
            print(f"❌ {args.code} 不在 today.json 里")
            return
        rec = review_one(today["date"], args.code, s["name"], s["entry_price"], args.close, args.note)
        history.append(rec)
        save_history(history)
        print(f"✅ {rec['name']}（{rec['code']}）{rec['pct']:+.2f}% [{rec['result']}]")

    else:
        parser.print_help()
        print("\n示例:")
        print("  python review.py --batch")
        print("  python review.py 600519 1735")
        return

    # 更新汇总
    summary = calc_summary(history)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n📊 累计: {summary['wins']}胜 {summary['losses']}负 / 共{summary['total']}只 / 胜率 {summary['win_rate']}% / 平均 {summary['avg_pct']:+.2f}%")
    print(f"   最佳: {summary['best']}% | 最差: {summary['worst']}%")


if __name__ == "__main__":
    main()