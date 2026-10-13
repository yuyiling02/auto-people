"""
Image Generator - 本地图片生成程序

功能：
  1. 纯色图
  2. 线性渐变图
  3. 径向渐变图
  4. 噪声纹理图
  5. 几何图形艺术
  6. 文字海报
  7. AI 生图（OpenAI 兼容接口，默认模型 gpt-image-2）
  8. 英文非官方文档设计稿（课程表 / 学生卡 / 费用收据）

用法：
  python image_generator.py --mode gradient --width 1920 --height 1080 --output out.png
  python image_generator.py --mode ai --prompt "一只在月球上的猫" --output ai.png
  python image_generator.py --mode documents --output umgc.png
"""

import argparse
import math
import os
import random
import sys
import zipfile

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    sys.stderr.write("缺少 Pillow，请先运行: pip install Pillow\n")
    sys.exit(1)


# ------------------------------------------------------------ AI 生图配置
from image_api import make_ai_image
from document_generator import generate_document_set

DEFAULT_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://localhost:3000/v1")
DEFAULT_AI_MODEL = "gpt-image-2"

# ---------------------------------------------------------------- 1. 纯色图
def make_solid(width, height, color):
    return Image.new("RGB", (width, height), color)


# ------------------------------------------------------------ 2. 线性渐变
def make_linear_gradient(width, height, color1, color2, angle=0):
    """生成从 color1 到 color2 的线性渐变。angle 单位为弧度。"""
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    for y in range(height):
        for x in range(width):
            nx = x / max(width - 1, 1)
            ny = y / max(height - 1, 1)
            t = nx * cos_a + ny * sin_a
            t = max(0.0, min(1.0, t))
            r = int(color1[0] + (color2[0] - color1[0]) * t)
            g = int(color1[1] + (color2[1] - color1[1]) * t)
            b = int(color1[2] + (color2[2] - color1[2]) * t)
            pixels[x, y] = (r, g, b)
    return img


# ------------------------------------------------------------ 3. 径向渐变
def make_radial_gradient(width, height, color_center, color_edge):
    img = Image.new("RGB", (width, height))
    pixels = img.load()
    cx, cy = width / 2, height / 2
    max_dist = math.hypot(cx, cy)
    for y in range(height):
        for x in range(width):
            d = math.hypot(x - cx, y - cy) / max_dist
            d = min(d, 1.0)
            r = int(color_center[0] + (color_edge[0] - color_center[0]) * d)
            g = int(color_center[1] + (color_edge[1] - color_center[1]) * d)
            b = int(color_center[2] + (color_edge[2] - color_center[2]) * d)
            pixels[x, y] = (r, g, b)
    return img


# ------------------------------------------------------------ 4. 噪声纹理
def make_noise(width, height, base_color, noise_amount=30):
    img = Image.new("RGB", (width, height), base_color)
    pixels = img.load()
    for y in range(height):
        for x in range(width):
            n = random.randint(-noise_amount, noise_amount)
            r = max(0, min(255, base_color[0] + n))
            g = max(0, min(255, base_color[1] + n))
            b = max(0, min(255, base_color[2] + n))
            pixels[x, y] = (r, g, b)
    return img


# -------------------------------------------------------- 5. 几何图形艺术
def make_geometric_art(width, height, palette, count=40):
    img = Image.new("RGB", (width, height), (245, 245, 245))
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        shape = random.choice(["rect", "ellipse", "triangle", "line"])
        color = random.choice(palette)
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        lx, rx = sorted([x1, x2])
        ty, by = sorted([y1, y2])
        if shape == "rect":
            draw.rectangle([lx, ty, rx, by], fill=color)
        elif shape == "ellipse":
            draw.ellipse([lx, ty, rx, by], fill=color)
        elif shape == "triangle":
            points = [(random.randint(0, width), random.randint(0, height)) for _ in range(3)]
            draw.polygon(points, fill=color)
        elif shape == "line":
            draw.line([x1, y1, x2, y2], fill=color, width=random.randint(1, 8))
    img = img.filter(ImageFilter.GaussianBlur(0.5))
    return img


# ------------------------------------------------------------ 6. 文字海报
def _find_font(size):
    """尝试加载系统字体；失败返回 None。"""
    for candidate in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            ImageFont.truetype(candidate, size)
            return candidate
        except Exception:
            continue
    return None


def make_text_poster(width, height, title, subtitle="", bg=(20, 40, 80), fg=(255, 255, 255)):
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    title_size = max(24, width // 12)
    subtitle_size = max(16, width // 24)
    font_path = _find_font(title_size)
    if font_path:
        title_font = ImageFont.truetype(font_path, title_size)
    else:
        title_font = ImageFont.load_default()

    sub_path = _find_font(subtitle_size)
    if sub_path:
        sub_font = ImageFont.truetype(sub_path, subtitle_size)
    else:
        sub_font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), title, font=title_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, (height - th) // 2 - th // 2), title, font=title_font, fill=fg)

    if subtitle:
        bbox2 = draw.textbbox((0, 0), subtitle, font=sub_font)
        sw = bbox2[2] - bbox2[0]
        draw.text(((width - sw) // 2, (height + th) // 2 + 20), subtitle, font=sub_font, fill=fg)
    return img


# ---------------------------------------------------------- 7. AI 生图
def _derive_size(width, height):
    """把任意宽高映射到 gpt-image 系列支持的尺寸。"""
    if width == height:
        return "1024x1024"
    if width > height:
        return "1536x1024"
    return "1024x1536"


# ---------------------------------------------------------------- CLI 入口
def parse_color(s):
    s = s.strip().lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main():
    parser = argparse.ArgumentParser(description="本地图片生成程序")
    parser.add_argument("--mode", required=True,
                        choices=["solid", "gradient", "radial", "noise", "art", "poster", "ai", "documents"],
                        help="生成模式")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--color1", type=str, default="#003366")
    parser.add_argument("--color2", type=str, default="#FFCC00")
    parser.add_argument("--output", type=str, default="generated.png")
    parser.add_argument("--title", type=str, default="示例标题")
    parser.add_argument("--subtitle", type=str, default="")
    parser.add_argument("--count", type=int, default=40)
    parser.add_argument("--prompt", type=str, default="",
                        help="AI 生图提示词（mode=ai 时必填）")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL,
                        help="OpenAI 兼容 API 地址")
    parser.add_argument("--api-key", type=str, default=None,
                        help="API 密钥（推荐使用 OPENAI_API_KEY 环境变量）")
    parser.add_argument("--model", type=str, default=DEFAULT_AI_MODEL,
                        help="AI 生图模型，默认 gpt-image-2")
    parser.add_argument("--size", type=str, default=None,
                        help="AI 生图尺寸，如 1024x1024；默认根据宽高自动推导")
    parser.add_argument("--base-name", type=str, default="umgc_doc",
                        help="文档套图文件名前缀（mode=documents）")
    parser.add_argument("--resource-zip", help="学校公开资料 ZIP，仅按数据读取")
    parser.add_argument("--profile", default="profile.json", help="持久化虚构人物档案")
    parser.add_argument("--new-profile", action="store_true", help="创建独立的新人物档案")
    parser.add_argument("--seed", type=int, help="新人物的可复现随机种子")
    parser.add_argument("--out-dir", default="outputs", help="文档批次输出根目录")
    parser.add_argument("--resume", help="继续已有文档批次，沿用锁定的人物与模型")
    parser.add_argument("--render-mode", choices=["ai", "local"], default="ai",
                        help="文档素材模式；local 仅为显式选择的离线排版预览")
    parser.add_argument("--timeout", type=float, default=300, help="AI 请求超时秒数")
    args = parser.parse_args()

    args.api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if args.mode == "documents":
        if (args.width is None) != (args.height is None):
            parser.error("文档缩放需要同时指定 --width 和 --height")
        output_size = (args.width, args.height) if args.width is not None else None
        batch, outputs = generate_document_set(
            profile_path=args.profile, resource_zip=args.resource_zip, out_dir=args.out_dir,
            base_name=args.base_name, seed=args.seed, new_profile=args.new_profile,
            resume=args.resume, render_mode=args.render_mode, base_url=args.base_url,
            api_key=args.api_key, model=args.model, timeout=args.timeout, output_size=output_size,
        )
        print(f"Batch complete: {batch}")
        for path in outputs:
            print(f"Generated: {path}")
        if args.resume:
            print("Rendering: see job.json for the locked rendering mode")
        elif args.render_mode == "local":
            print("Rendering: LOCAL PREVIEW ONLY; no AI request was made")
        else:
            print("Rendering: AI assets with local typesetting")
        return

    args.width = args.width if args.width is not None else 1920
    args.height = args.height if args.height is not None else 1080
    if min(args.width, args.height) < 1:
        parser.error("图片宽高必须为正数")

    c1 = parse_color(args.color1)
    c2 = parse_color(args.color2)

    if args.mode == "solid":
        img = make_solid(args.width, args.height, c1)
    elif args.mode == "gradient":
        img = make_linear_gradient(args.width, args.height, c1, c2)
    elif args.mode == "radial":
        img = make_radial_gradient(args.width, args.height, c1, c2)
    elif args.mode == "noise":
        img = make_noise(args.width, args.height, c1)
    elif args.mode == "art":
        palette = [c1, c2, (255, 255, 255), (30, 30, 30)]
        img = make_geometric_art(args.width, args.height, palette, args.count)
    elif args.mode == "poster":
        img = make_text_poster(args.width, args.height, args.title, args.subtitle, c1, (255, 255, 255))
    elif args.mode == "ai":
        if not args.prompt:
            sys.stderr.write("错误: mode=ai 时必须通过 --prompt 提供提示词\n")
            sys.exit(2)
        size = args.size or _derive_size(args.width, args.height)
        print(f"AI 生图中: model={args.model}, size={size}, prompt={args.prompt!r} ...")
        img = make_ai_image(args.prompt, args.base_url, args.api_key, args.model, size, args.timeout)
        args.width, args.height = img.size

    img.save(args.output)
    print(f"已生成: {args.output}  ({args.width}x{args.height}, 模式={args.mode})")


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        main()
    except (ValueError, RuntimeError, OSError, KeyError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
