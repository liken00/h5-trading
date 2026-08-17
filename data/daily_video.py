#!/usr/bin/env python3
"""9:25 龙头复盘短视频生成器

用法:
  python daily_video.py                       # 读 today.json 自动生成 30 秒视频
  python daily_video.py --stocks file.json    # 用自定义 JSON
  python daily_video.py --duration 60         # 自定义时长（秒）

输出:
  data/videos/YYYY-MM-DD_daily_review.mp4     (1080×1920, ~30 秒)

流程:
  today.json → 生成 TTS 文案 → edge-tts 配音
  → Pillow 生成竖屏字幕帧（黑底 + 白字 + 战法要点）
  → ffmpeg 合成 mp4
"""
import os
import sys
import json
import argparse
import asyncio
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

# === 路径配置 ===
DATA_DIR = r"C:\Users\Administrator\AppData\Local\hermes\projects\h5-trading\data"
VIDEOS_DIR = os.path.join(DATA_DIR, "videos")
TODAY_PATH = os.path.join(DATA_DIR, "today.json")
TEMP_DIR = r"C:\Users\Administrator\AppData\Local\Temp"

# === ffmpeg（imageio 自带）===
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
print(f"[ffmpeg] {FFMPEG}")

# === 中文字体（Windows 自带）===
FONT_PATH = r"C:\Windows\Fonts\msyh.ttc"

# === 视频参数 ===
WIDTH, HEIGHT = 1080, 1920  # 9:16 竖屏
FPS = 30
BG_COLOR = (15, 18, 28)       # 深蓝黑
ACCENT = (88, 166, 255)       # GitHub 蓝
TEXT = (235, 237, 243)        # 近白
MUTED = (139, 148, 158)       # 灰
RED = (248, 81, 73)           # 红（风险提示）
GREEN = (63, 185, 80)         # 绿（机会）
GOLD = (210, 153, 34)         # 金（重点）


def make_script(stocks):
    """生成 30 秒 TTS 文案（按节奏切段，严格控制总字数）

    结构（严格控制字数）：
      [0-3s]  钩子（≤ 12 字）
      [3-9s]  总览（≤ 14 字）
      [9-22s] 5 只速览（每只 ≤ 18 字，约 2.5s）
      [22-27s] 风险提示（≤ 18 字）
      [27-30s] CTA（≤ 14 字）

    设计原则：
      - 字数越少，TTS 读得越快 → 时长越精准
      - 段时长按字数预估：~3 字/s（中文）
    """
    segments = []
    # 钩子
    segments.append({
        "text": f"今日龙头{len(stocks)}只。",
        "duration": 3.0
    })
    # 总览（用首只的策略标签）
    main_strategy = stocks[0].get("strategy", "战法精选") if stocks else "战法精选"
    # 截短策略标签（≤ 12 字）
    short_strat = main_strategy.replace("连板数", "连板").replace("涨幅", "涨")[:12]
    segments.append({
        "text": f"{short_strat}，今日精选。",
        "duration": 6.0
    })
    # 5 只速览（精简到 ≤ 16 字）
    for s in stocks[:5]:
        name = s.get("name", "")[:4]   # 名称限 4 字
        code = s.get("code", "")       # 6 位代码
        # 战法限 4 字
        strat = s.get("strategy", "").replace("连板数", "").replace("涨幅", "").strip()[:4]
        text = f"{name} {code} {strat}。"
        segments.append({
            "text": text,
            "duration": 2.6
        })
    # 风险
    segments.append({
        "text": "仅供学习，非投资建议。",
        "duration": 5.0
    })
    # CTA
    segments.append({
        "text": "关注复盘宝，9点25准时。",
        "duration": 3.0
    })
    return segments


async def generate_tts(text, output_path, voice="zh-CN-XiaoxiaoNeural"):
    """edge-tts 生成配音"""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice, rate="+0%")
    await communicate.save(output_path)


def get_audio_duration(audio_path):
    """从 ffmpeg stderr 解析音频时长（不需要 ffprobe）"""
    result = subprocess.run(
        [FFMPEG, "-i", audio_path, "-f", "null", "-"],
        capture_output=True, text=True
    )
    # stderr 里有 "Duration: HH:MM:SS.xx"
    import re
    m = re.search(r"Duration:\s+(\d+):(\d+):(\d+\.\d+)", result.stderr)
    if m:
        h, mn, s = m.groups()
        return float(h) * 3600 + float(mn) * 60 + float(s)
    return None


def render_frame(width, height, segments_timings, current_time, frame_idx):
    """渲染单帧（Pillow）

    改进点：
      - 打字机系数 1.2 → 1.0（精准显示，不裁字）
      - 底部信息居中（避免裁切）
      - 底部信息缩短
    """
    # 找当前时间段
    seg = segments_timings[-1]
    for s in segments_timings:
        if s["start"] <= current_time < s["end"]:
            seg = s
            break

    # 背景
    img = Image.new("RGB", (width, height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 顶部 logo 区
    logo_font = ImageFont.truetype(FONT_PATH, 36)
    draw.text((60, 80), "🐉 复盘宝 · 龙头复盘", fill=GOLD, font=logo_font)

    # 分隔线
    draw.line([(60, 140), (width - 60, 140)], fill=MUTED, width=2)

    # 时间码
    time_font = ImageFont.truetype(FONT_PATH, 28)
    draw.text((60, 170), datetime.now().strftime("%Y-%m-%d"), fill=MUTED, font=time_font)

    # 主字幕（中段）
    time_in_seg = current_time - seg["start"]
    seg_dur = seg["end"] - seg["start"]

    # 打字机效果：精确控制（系数 1.0 = 段末刚好显示完整）
    full_text = seg["text"]
    # 用平滑曲线（start 时 0, end 时 len）
    progress = min(time_in_seg / seg_dur, 1.0)
    chars_to_show = int(len(full_text) * progress)
    display_text = full_text[:chars_to_show]

    # 主字幕（中心偏上）
    main_font = ImageFont.truetype(FONT_PATH, 78)
    lines = []
    # 中文按 14 字/行换行
    line_text = display_text
    while len(line_text) > 14:
        lines.append(line_text[:14])
        line_text = line_text[14:]
    if line_text:
        lines.append(line_text)

    # 文字框
    line_h = 100
    y_start = height // 2 - len(lines) * line_h // 2 - 100

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=main_font)
        lw = bbox[2] - bbox[0]
        x = (width - lw) // 2
        y = y_start + i * line_h
        # 半透明黑色底框
        pad_x, pad_y = 40, 20
        rect = Image.new("RGBA", (width, line_h + pad_y * 2), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rect)
        rd.rectangle([0, 0, width, line_h + pad_y * 2], fill=(0, 0, 0, 100))
        img.paste(rect, (0, y - pad_y), rect)
        # 文字
        draw.text((x, y), line, fill=TEXT, font=main_font)

    # 底部：进度条
    progress = current_time / segments_timings[-1]["end"]
    bar_w = width - 120
    draw.rectangle([(60, height - 60), (60 + bar_w, height - 50)], fill=(40, 50, 60))
    draw.rectangle([(60, height - 60), (60 + int(bar_w * progress), height - 50)], fill=ACCENT)

    # 底部信息（居中 + 简短）
    info_font = ImageFont.truetype(FONT_PATH, 24)
    info_text = f"第 {int(current_time) + 1} 秒 · 30 秒看完今日龙头"
    bbox = draw.textbbox((0, 0), info_text, font=info_font)
    iw = bbox[2] - bbox[0]
    draw.text(((width - iw) // 2, height - 130), info_text, fill=MUTED, font=info_font)

    return img


def generate_video(stocks, output_path, duration=None):
    """主流程"""
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(TEMP_DIR, exist_ok=True)

    # 1. 生成文案
    segments = make_script(stocks)
    full_text = " ".join(s["text"] for s in segments)

    print(f"[1/4] 文案: {full_text[:80]}...")

    # 2. TTS 配音
    audio_path = os.path.join(TEMP_DIR, f"daily_tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3")
    print(f"[2/4] TTS 配音: {audio_path}")
    asyncio.run(generate_tts(full_text, audio_path))

    # 测时长
    audio_dur = get_audio_duration(audio_path)
    if not audio_dur:
        raise RuntimeError("无法测音频时长")
    print(f"      音频时长: {audio_dur:.1f}s")

    # 用音频实际时长作为视频时长
    total_duration = duration if duration else audio_dur + 0.5
    print(f"      视频时长: {total_duration:.1f}s")

    # 3. 算每段时间
    total_text_dur = sum(s["duration"] for s in segments)
    scale = total_duration / total_text_dur
    cursor = 0.0
    for s in segments:
        s["start"] = cursor
        s["end"] = cursor + s["duration"] * scale
        cursor = s["end"]

    # 4. 生成字幕帧 + ffmpeg 合成
    frames_dir = os.path.join(TEMP_DIR, f"daily_frames_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(frames_dir, exist_ok=True)

    total_frames = int(total_duration * FPS)
    print(f"[3/4] 生成字幕帧: {total_frames} 帧 @ {FPS}fps")

    for i in range(total_frames):
        t = i / FPS
        img = render_frame(WIDTH, HEIGHT, segments, t, i)
        img.save(os.path.join(frames_dir, f"frame_{i:05d}.png"), quality=85)
        if (i + 1) % 60 == 0:
            print(f"      已生成 {i+1}/{total_frames} 帧 ({100*(i+1)/total_frames:.0f}%)")

    # 5. ffmpeg 合成
    print(f"[4/4] ffmpeg 合成: {output_path}")
    cmd = [
        FFMPEG, "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.png"),
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    # 清理临时帧
    for f in os.listdir(frames_dir):
        os.remove(os.path.join(frames_dir, f))
    os.rmdir(frames_dir)
    os.remove(audio_path)

    print(f"\n✅ 视频生成完成: {output_path}")
    print(f"   大小: {os.path.getsize(output_path) / 1024:.1f} KB")
    print(f"   时长: ~{total_duration:.0f} 秒")
    print(f"   分辨率: {WIDTH}×{HEIGHT}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="9:25 龙头复盘短视频生成器")
    parser.add_argument("--stocks", help="自定义股票 JSON 路径")
    parser.add_argument("--duration", type=float, help="自定义时长（秒）")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    # 读 today.json
    src = args.stocks or TODAY_PATH
    if not os.path.exists(src):
        print(f"❌ {src} 不存在")
        return
    with open(src, "r", encoding="utf-8") as f:
        data = json.load(f)
    stocks = data.get("stocks", [])
    if not stocks:
        print(f"❌ {src} 里没有 stocks 数据")
        return

    print(f"=== 9:25 龙头复盘短视频生成器 ===")
    print(f"  日期: {data.get('date', 'unknown')}")
    print(f"  标的数: {len(stocks)}")
    print()

    # 输出路径
    date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    if args.output:
        output = args.output
    else:
        os.makedirs(VIDEOS_DIR, exist_ok=True)
        output = os.path.join(VIDEOS_DIR, f"{date}_daily_review.mp4")

    generate_video(stocks, output, args.duration)


if __name__ == "__main__":
    main()