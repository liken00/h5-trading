#!/usr/bin/env python3
"""5 平台推送文案生成器

用法:
  python generate_posts.py                   # 读 today.json + 输出
  python generate_posts.py --platform xiaohongshu    # 只输出 1 个平台

平台: 抖音 30s / 小红书图文 / 视频号 / B 站长视频 / 公众号
"""
import os
import sys
import json
import argparse
from datetime import datetime

DATA_DIR = r"C:\Users\Administrator\AppData\Local\hermes\projects\h5-trading\data"
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
POSTS_DIR = os.path.join(DATA_DIR, "posts")


def load_today():
    with open(TODAY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def gen_douyin_script(data):
    """抖音 30 秒脚本 — 钩子 + 战法 + 5 只速览 + CTA"""
    stocks = data.get("stocks", [])
    date = data.get("date", "")
    summary = data.get("summary", "")

    # 钩子
    hook = f"今天 {len(stocks)} 只龙头候选，战法依据 + 买卖点全公开"

    # 战法概述
    body_lines = [
        f"【龙韵智趋】{date} 复盘",
        f"战法依据：{summary}",
        "",
    ]

    # 5 只速览
    for i, s in enumerate(stocks[:5], 1):
        name = s.get("name", "")
        code = s.get("code", "")
        strategy = s.get("strategy", "")[:30]  # 截断
        body_lines.append(f"{i}. {name}（{code}）— {strategy}")

    body = "\\n".join(body_lines)

    # CTA
    cta = "完整版（含买卖点 + 止损价）→ 主页链接"

    return {
        "title": hook,
        "duration": "30秒",
        "scenes": [
            {"time": "0-3s", "visual": "黑屏大字「今日 5 只龙头」", "voice": hook},
            {"time": "4-12s", "visual": "K 线图 + 战法依据", "voice": summary},
            {"time": "13-25s", "visual": "5 只速览卡片", "voice": body},
            {"time": "26-30s", "visual": "主页二维码", "voice": cta}
        ],
        "hashtags": ["#股票", "#短线", "#涨停", "#龙头股", "#战法", "#复盘宝"],
        "publish_time": "09:30 / 12:00 / 20:00"
    }


def gen_xiaohongshu_post(data):
    """小红书 9 图笔记"""
    stocks = data.get("stocks", [])
    date = data.get("date", "")

    title = f"{date} | 9:25 选股战法公开，{len(stocks)} 只龙头候选"

    # 9 张图内容
    images = [
        f"封面：{date} 涨停复盘 | {len(stocks)} 只龙头",
        f"为什么今天选这 {len(stocks)} 只？双二板 + MA10 回调战法",
        f"战法核心：蛰伏 → 双二板定主线 → 三/四板定龙头 → MA10 回调",
    ]
    for i, s in enumerate(stocks[:5], 1):
        images.append(
            f"#{i} {s.get('name', '')}（{s.get('code', '')}）\n"
            f"战法：{s.get('strategy', '')}\n"
            f"买入：{s.get('entry_price', '-')}  目标：{s.get('target_price', '-')}\n"
            f"止损：{s.get('stop_loss', '-')}  仓位：{s.get('position', '-')}"
        )
    # 补足 9 张
    while len(images) < 9:
        images.append("复盘宝 — 9:25 准时公布 | 主页有完整战法")

    body = (
        f"今天分享 {date} 9:25 集合竞价后的选股战法\n"
        f"基于龙韵智趋（双二板 + MA10 回调）战法，5 只龙头候选。\n\n"
        f"📌 战法核心：\n"
        f"1. 同板块 ≥2 只同日 2 板 = 主线确认\n"
        f"2. 三/四板封板时间最早 = 龙头\n"
        f"3. ≥4 板回调 MA10 + 缩量承接 = 买点\n\n"
        f"📊 5 只速览见图片\n"
        f"💡 完整战法 + 每日复盘：主页有链接\n"
        f"#股票 #短线 #涨停 #龙头 #战法 #复盘宝 #龙韵智趋"
    )

    return {
        "title": title,
        "type": "9图图文",
        "images": images,
        "body": body,
        "hashtags": ["#股票", "#短线", "#涨停", "#龙头股", "#战法"],
        "publish_time": "09:30 - 10:00"
    }


def gen_wechat_video_script(data):
    """视频号脚本（横版 60 秒）"""
    stocks = data.get("stocks", [])
    return {
        "title": f"{data.get('date', '')} 9:25 选股 | 战法依据",
        "duration": "60秒",
        "scenes": [
            {"time": "0-5s", "visual": "标题卡", "voice": "9:25 集合竞价结束，今天有 5 只龙头候选"},
            {"time": "5-20s", "visual": "战法图解", "voice": data.get("summary", "")},
            {"time": "20-50s", "visual": "5 只速览", "voice": "详细战法依据在公众号文章"},
            {"time": "50-60s", "visual": "公众号二维码", "voice": "关注公众号，回复「战法」看完整版"}
        ],
        "publish_time": "09:30"
    }


def gen_bilibili_script(data):
    """B 站 5-8 分钟长视频脚本"""
    stocks = data.get("stocks", [])
    return {
        "title": f"【龙韵智趋】{data.get('date', '')} 9:25 选股战法详解 | 5 只龙头候选",
        "duration": "5-8分钟",
        "outline": [
            f"00:00 - 开场：{data.get('date', '')} 大盘 + 战法回顾",
            "00:30 - 战法核心：双二板 → 三/四板 → MA10 回调",
            "02:00 - 5 只龙头候选详细分析（含战法依据）",
            f"   1. {stocks[0].get('name', '')}（{stocks[0].get('code', '')}）— {stocks[0].get('strategy', '')[:30]}" if stocks else "",
            f"   2. {stocks[1].get('name', '')}（{stocks[1].get('code', '')}）— {stocks[1].get('strategy', '')[:30]}" if len(stocks) > 1 else "",
            f"   3. {stocks[2].get('name', '')}（{stocks[2].get('code', '')}）— {stocks[2].get('strategy', '')[:30]}" if len(stocks) > 2 else "",
            f"   4. {stocks[3].get('name', '')}（{stocks[3].get('code', '')}）— {stocks[3].get('strategy', '')[:30]}" if len(stocks) > 3 else "",
            f"   5. {stocks[4].get('name', '')}（{stocks[4].get('code', '')}）— {stocks[4].get('strategy', '')[:30]}" if len(stocks) > 4 else "",
            "05:00 - 战法三件套：30分钟 MA50 + 日K MA10 ± 5% + 缩量承接",
            "06:00 - 风险提示 + 完整战法课程入口"
        ],
        "publish_time": "周末 09:00"
    }


def gen_wechat_official(data):
    """公众号长文（白皮书风格）"""
    stocks = data.get("stocks", [])
    date = data.get("date", "")

    body = f"""# {date} 9:25 龙头候选 | 龙韵智趋战法公开

> 作者：复盘宝 · 智趋学堂
> 阅读时长：5 分钟

## 一、今日选股战法依据

{data.get("summary", "")}

## 二、5 只龙头候选详细分析

"""

    for i, s in enumerate(stocks, 1):
        body += f"""### {i}. {s.get("name", "")}（{s.get("code", "")}）

**战法依据**：{s.get("strategy", "")}

- **买入价**：{s.get("entry_price", "-")}
- **目标价**：{s.get("target_price", "-")}
- **止损价**：{s.get("stop_loss", "-")}
- **建议仓位**：{s.get("position", "-")}
- **标签**：{" / ".join(s.get("tags", []))}

{s.get("note", "")}

---

"""

    body += """## 三、战法核心回顾

1. **双二板定主线**：同板块 ≥2 只同日 2 板 = 主线确认
2. **三/四板定龙头**：三/四板封板时间最早 = 龙头
3. **MA10 回调买点**：≥4 板回调 MA10 + 缩量承接 = 二波买点

## 四、风险提示

- 本内容仅供学习参考，不构成投资建议
- 股市有风险，入市需谨慎
- 战法需结合实盘验证，切勿盲目跟单

---

📚 **完整 30 节战法系统课** → 关注公众号，回复「战法」领取大纲
"""

    return {
        "title": f"{date} 9:25 龙头候选 | 龙韵智趋战法公开",
        "type": "公众号长文",
        "body": body,
        "word_count": len(body),
        "publish_time": "09:30 群发 + 20:00 备用"
    }


PLATFORMS = {
    "douyin": gen_douyin_script,
    "xiaohongshu": gen_xiaohongshu_post,
    "wechat_video": gen_wechat_video_script,
    "bilibili": gen_bilibili_script,
    "wechat": gen_wechat_official,
}


def main():
    parser = argparse.ArgumentParser(description="5 平台推送文案生成器")
    parser.add_argument("--platform", choices=list(PLATFORMS.keys()) + ["all"],
                        default="all", help="指定平台（默认 all）")
    args = parser.parse_args()

    data = load_today()
    print(f"=== 5 平台文案生成 | {data.get('date', '')} ===\n")

    os.makedirs(POSTS_DIR, exist_ok=True)

    platforms = list(PLATFORMS.keys()) if args.platform == "all" else [args.platform]
    results = {}

    for plat in platforms:
        gen_fn = PLATFORMS[plat]
        result = gen_fn(data)
        results[plat] = result

        # 保存每个平台单独文件
        fname = os.path.join(POSTS_DIR, f"{data.get('date', '')}_{plat}.json")
        with open(fname, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        print(f"✅ {plat}: {fname}")

    # 汇总
    summary_path = os.path.join(POSTS_DIR, f"{data.get('date', '')}_all.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n📦 汇总: {summary_path}")
    print(f"\n💡 下一步: 复制各平台内容到对应 app 发布")


if __name__ == "__main__":
    main()