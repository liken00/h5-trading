#!/usr/bin/env python3
"""OpenClaw 自动选股脚本

每天 9:30 (集合竞价后) 自动调用 akshare 跑选股
把结果写入 today.json，触发 H5 推送
"""
import os
import json
import sys
from datetime import datetime

# akshare 实时选股
import akshare as ak
import pandas as pd

DATA_DIR = r"C:\Users\Administrator\AppData\Local\hermes\projects\h5-trading\data"
TODAY_PATH = os.path.join(DATA_DIR, "today.json")


def fetch_zt_pool(date=None):
    """拉今日涨停股池"""
    if not date:
        date = datetime.now().strftime("%Y%m%d")
    try:
        df = ak.stock_zt_pool_em(date=date)
        return df
    except Exception as e:
        print(f"akshare 涨停拉取失败: {e}")
        return pd.DataFrame()


def filter_double_second_board(df):
    """双二板筛选（同板块≥2只同日 2 板 = 主线）

    规则: 同板块 ≥2 只 连板数 >= 2 (即 2 板及以上)
    """
    if df.empty:
        return []
    mainlines = []
    if "所属行业" not in df.columns:
        return mainlines
    for board in df["所属行业"].unique():
        sub = df[df["所属行业"] == board]
        # 连板数 >= 2 (二板及以上)
        two_plus = sub[sub["连板数"] >= 2]
        if len(two_plus) >= 2:
            # 找最长的连板
            max_boards = int(two_plus["连板数"].max())
            mainlines.append({
                "sector": board,
                "count": len(two_plus),
                "max_boards": max_boards,
                "stocks": two_plus["名称"].tolist()[:5]
            })
    # 按 count 降序
    mainlines.sort(key=lambda x: x["count"], reverse=True)
    return mainlines


def select_top5(df):
    """从前 20 只涨停股里选 5 只龙头候选"""
    if df.empty:
        return []
    # 列名兼容: "涨幅" / "涨跌幅" 两种
    pct_col = "涨跌幅" if "涨跌幅" in df.columns else "涨幅"
    # 排序：连板数降序、涨跌幅降序
    df_sorted = df.sort_values(["连板数", pct_col], ascending=[False, False]).head(20)
    candidates = []
    for _, row in df_sorted.head(5).iterrows():
        try:
            latest_price = float(row.get("最新价", 0))
        except (ValueError, TypeError):
            latest_price = 0
        try:
            pct = float(row.get(pct_col, 0))
        except (ValueError, TypeError):
            pct = 0
        candidates.append({
            "code": str(row.get("代码", "")),
            "name": str(row.get("名称", "")),
            "strategy": f"连板数 {row.get('连板数', 0)} | 涨幅 {pct:.1f}%",
            "entry_price": round(latest_price * 1.005, 2) if latest_price > 0 else 0,
            "target_price": round(latest_price * 1.05, 2) if latest_price > 0 else 0,
            "stop_loss": round(latest_price * 0.97, 2) if latest_price > 0 else 0,
            "position": "0.25成" if row.get("连板数", 0) < 4 else "0.35成",
            "tags": ["主线", "涨停"],
            "note": f"自动选股 - 选自{row.get('所属行业', '')}板块"
        })
    return candidates


def main():
    date = datetime.now().strftime("%Y-%m-%d")
    publish_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"=== 自动选股 {date} ===")
    df = fetch_zt_pool()
    print(f"涨停股池: {len(df)} 只")

    mainlines = filter_double_second_board(df)
    print(f"主线板块: {len(mainlines)} 个")
    for m in mainlines:
        print(f"  - {m['sector']}: {m['count']} 只")

    candidates = select_top5(df)
    print(f"\n选股 5 只:")
    for c in candidates:
        print(f"  - {c['code']} {c['name']} ({c['strategy']})")

    # 写 today.json
    data = {
        "date": date,
        "publish_time": publish_time,
        "title": f"今日 {len(candidates)} 只龙头候选 (自动)",
        "summary": f"双二板主线 {len(mainlines)} 个 | 自动扫描全市场涨停股池",
        "stocks": candidates
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TODAY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入: {TODAY_PATH}")
    print("下一步: python data/publish.py 推到 GitHub Pages")


if __name__ == "__main__":
    main()