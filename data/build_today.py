#!/usr/bin/env python3
"""今日选股数据生成器

用法:
  python build_today.py 600519 贵州茅台 双二板+MA10 1680 1750 1650 0.35 消费,主线
  python build_today.py --demo    # 用示例数据填进去
  python build_today.py --file codes.txt    # 从文件读

每个参数:
  代码 名称 战法 买入价 目标价 止损价 仓位 标签

标签用英文逗号分隔
"""
import sys
import json
import os
import argparse
from datetime import datetime

DATA_DIR = r"C:\Users\Administrator\AppData\Local\hermes\projects\h5-trading\data"
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
HISTORY_PATH = os.path.join(DATA_DIR, "history.jsonl")


# 示例数据（用作演示 + 试跑）
DEMO_STOCKS = [
    {
        "code": "600519",
        "name": "贵州茅台",
        "strategy": "双二板+4板回调MA10",
        "entry_price": 1680.00,
        "target_price": 1750.00,
        "stop_loss": 1650.00,
        "position": "0.35成",
        "tags": ["主线", "消费"],
        "note": "今日主推"
    },
    {
        "code": "000858",
        "name": "五粮液",
        "strategy": "主线共振+板块共振",
        "entry_price": 158.00,
        "target_price": 168.00,
        "stop_loss": 154.00,
        "position": "0.25成",
        "tags": ["主线", "消费"],
        "note": "白酒二梯队"
    },
    {
        "code": "601318",
        "name": "中国平安",
        "strategy": "3板后回踩MA10",
        "entry_price": 45.50,
        "target_price": 48.00,
        "stop_loss": 44.50,
        "position": "0.25成",
        "tags": ["主线", "金融"],
        "note": "金融龙头"
    },
    {
        "code": "300750",
        "name": "宁德时代",
        "strategy": "二波启动+MA10支撑",
        "entry_price": 215.00,
        "target_price": 230.00,
        "stop_loss": 210.00,
        "position": "0.35成",
        "tags": ["二波", "新能源"],
        "note": "新能源龙头"
    },
    {
        "code": "002594",
        "name": "比亚迪",
        "strategy": "MA10支撑+缩量承接",
        "entry_price": 245.00,
        "target_price": 260.00,
        "stop_loss": 240.00,
        "position": "0.25成",
        "tags": ["二波", "新能源"],
        "note": "新能源二梯队"
    },
]


def parse_argv_args(argv):
    """解析 argv 形式的参数"""
    stocks = []
    i = 1  # skip script name
    while i < len(argv):
        # 每 8 个参数一组
        if i + 7 < len(argv):
            try:
                code = argv[i]
                name = argv[i+1]
                strategy = argv[i+2]
                entry_price = float(argv[i+3])
                target_price = float(argv[i+4])
                stop_loss = float(argv[i+5])
                position = argv[i+6]
                tags = argv[i+7].split(",")
                stocks.append({
                    "code": code,
                    "name": name,
                    "strategy": strategy,
                    "entry_price": entry_price,
                    "target_price": target_price,
                    "stop_loss": stop_loss,
                    "position": position,
                    "tags": tags,
                    "note": ""
                })
                i += 8
            except (ValueError, IndexError) as e:
                print(f"参数解析错误 @{i}: {e}")
                break
        else:
            print(f"⚠️ 参数不足（需要 8 个/只），跳过 @{i}")
            break
    return stocks


def build_today(stocks):
    """生成 today.json"""
    today = datetime.now().strftime("%Y-%m-%d")
    publish_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    data = {
        "date": today,
        "publish_time": publish_time,
        "title": f"今日 {len(stocks)} 只龙头候选",
        "summary": "基于双二板 + MA10回调战法精选",
        "stocks": stocks,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TODAY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成: {TODAY_PATH}")
    print(f"   日期: {today}")
    print(f"   标的数: {len(stocks)}")
    for s in stocks:
        print(f"     - {s['code']} {s['name']} ({s['strategy']})")

    return TODAY_PATH


def main():
    parser = argparse.ArgumentParser(description="今日选股数据生成器")
    parser.add_argument("args", nargs="*", help="股票数据（每 8 个一组）")
    parser.add_argument("--demo", action="store_true", help="用示例数据")
    parser.add_argument("--file", help="从文件读（每行一只股票）")
    args = parser.parse_args()

    if args.demo:
        stocks = DEMO_STOCKS
        print("📦 使用示例数据（5 只贵州茅台/五粮液/中国平安/宁德时代/比亚迪）")
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            stocks = parse_argv_args(f.read().split())
    elif args.args:
        stocks = parse_argv_args([sys.argv[0]] + args.args)
    else:
        parser.print_help()
        print("\n示例:")
        print("  python build_today.py --demo")
        print("  python build_today.py 600519 贵州茅台 双二板+MA10 1680 1750 1650 0.35 主线,消费")
        return

    build_today(stocks)


if __name__ == "__main__":
    main()