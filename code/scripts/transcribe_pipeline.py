#!/usr/bin/env python3
"""
高顿课程视频批量转写流水线
流程：视频 → 提取音频 → VAD分段加速 → SenseVoice转写 → 后处理 → 输出Markdown

用法：
  python transcribe_pipeline.py <视频文件或目录> [输出目录]

依赖：ffmpeg, funasr, torch
"""
import os
import sys
import re
import json
import time
import subprocess
from pathlib import Path


def extract_audio(video_path: str, output_wav: str) -> bool:
    """从视频提取16kHz单声道WAV音频"""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        output_wav
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] ffmpeg提取音频失败: {result.stderr[-500:]}")
        return False
    return True


def postprocess_text(text: str) -> str:
    """后处理：去除特殊标记，清理文本，简单分段"""
    # 去除SenseVoice特殊标记
    text = re.sub(r'<\|[^|]+\|>', '', text)
    # 去除首尾空白
    text = text.strip()
    # 合并连续空格
    text = re.sub(r'\s+', ' ', text)
    return text


def transcribe_audio(wav_path: str, model) -> dict:
    """
    使用FunASR+VAD转写音频，返回文本和统计信息
    VAD分段加速，输出合并文本
    """
    print("  开始转写（VAD分段加速）...")
    t0 = time.time()

    res = model.generate(
        input=wav_path,
        language="zh",
        use_itn=True,
        batch_size_s=60,
    )

    elapsed = time.time() - t0

    # 合并所有segment的文本
    full_text = ""
    for item in res:
        text = postprocess_text(item.get("text", ""))
        if text:
            full_text += text + "。"

    # 获取音频总时长
    total_duration = 0
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", wav_path],
            capture_output=True, text=True
        )
        total_duration = float(probe.stdout.strip())
    except Exception:
        pass

    speed = total_duration / elapsed if elapsed > 0 else 0
    print(f"  转写完成: {elapsed:.1f}秒, 速度{speed:.1f}x实时, {len(res)}段")

    return {
        "text": full_text,
        "duration": total_duration,
        "elapsed": elapsed,
        "speed": speed,
        "segments": len(res),
        "chars": len(full_text)
    }


def split_into_paragraphs(text: str, max_len: int = 500) -> list:
    """将长文本按句号/问号/感叹号分段，每段不超过max_len字"""
    # 先按标点符号分割
    sentences = re.split(r'(?<=[。？！])', text)
    paragraphs = []
    current = ""

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if len(current) + len(s) > max_len and current:
            paragraphs.append(current)
            current = s
        else:
            current += s

    if current:
        paragraphs.append(current)

    return paragraphs


def save_markdown(result: dict, output_path: str, video_name: str):
    """将转写结果保存为Markdown"""
    text = result["text"]
    paragraphs = split_into_paragraphs(text)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# {video_name}\n\n")
        f.write(f"> 自动转写 | 时长{result['duration']/3600:.1f}小时 | "
                f"转写耗时{result['elapsed']/60:.1f}分钟 | "
                f"速度{result['speed']:.1f}x实时 | "
                f"约{result['chars']}字\n\n")

        for i, para in enumerate(paragraphs, 1):
            f.write(f"## 第{i}段\n\n")
            f.write(f"{para}\n\n")

    print(f"  已保存: {output_path} ({len(paragraphs)}段)")


def save_json(result: dict, output_path: str):
    """保存原始JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


def process_video(video_path: str, output_dir: str, model) -> bool:
    """处理单个视频：提取音频→转写→保存"""
    video_path = Path(video_path)
    video_name = video_path.stem
    print(f"\n{'='*60}")
    print(f"处理: {video_name}")
    print(f"{'='*60}")

    # 创建输出子目录
    video_output_dir = Path(output_dir) / video_name
    video_output_dir.mkdir(parents=True, exist_ok=True)

    wav_path = str(video_output_dir / "audio.wav")
    md_path = str(video_output_dir / "transcript.md")
    json_path = str(video_output_dir / "transcript.json")

    # 跳过已完成的
    if os.path.exists(md_path) and os.path.getsize(md_path) > 100:
        print(f"  已存在转写结果，跳过")
        return True

    # 1. 提取音频
    print("  [1/3] 提取音频...")
    if not extract_audio(str(video_path), wav_path):
        return False
    wav_size = os.path.getsize(wav_path) / 1024 / 1024
    print(f"  音频大小: {wav_size:.1f}MB")

    # 2. 转写
    print("  [2/3] 转写中...")
    result = transcribe_audio(wav_path, model)
    if not result["text"]:
        print("  [ERROR] 转写结果为空")
        return False

    # 3. 保存
    print("  [3/3] 保存结果...")
    save_markdown(result, md_path, video_name)
    save_json(result, json_path)

    # 清理临时音频文件（节省空间）
    os.remove(wav_path)
    print(f"  已清理临时音频")

    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python transcribe_pipeline.py <视频文件或目录> [输出目录]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "transcripts"

    # 收集视频文件
    video_files = []
    if os.path.isfile(input_path):
        video_files.append(input_path)
    elif os.path.isdir(input_path):
        for ext in ["*.mp4", "*.mkv", "*.avi", "*.mov"]:
            video_files.extend(Path(input_path).rglob(ext))
        video_files = [str(f) for f in video_files]
    else:
        print(f"错误: {input_path} 不存在")
        sys.exit(1)

    if not video_files:
        print("未找到视频文件")
        sys.exit(1)

    print(f"找到 {len(video_files)} 个视频文件")
    print(f"输出目录: {output_dir}")
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # 加载模型（只加载一次）
    print("\n加载FunASR模型 (SenseVoice + fsmn-vad)...")
    from funasr import AutoModel
    t0 = time.time()
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        disable_update=True,
    )
    print(f"模型加载完成: {time.time()-t0:.1f}秒")

    # 批量处理
    success = 0
    failed = 0
    for i, video in enumerate(video_files, 1):
        print(f"\n进度: [{i}/{len(video_files)}]")
        try:
            if process_video(video, output_dir, model):
                success += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  [ERROR] 处理失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"全部完成: 成功{success}, 失败{failed}")
    print(f"输出目录: {output_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
