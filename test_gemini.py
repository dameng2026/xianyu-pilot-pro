# -*- coding: utf-8 -*-
import json
import base64
import os
import re
import datetime
import urllib.request
import urllib.error

title = "【自动发货】2024最新Office安装包 安装后自动激活（有对应安装步骤）可选版本"
content = """【自动发货】2024最新Office安装包 安装后自动激活（有对应安装步骤）可选版本

一键快速下载、安装、部署最新 Microsoft Office 2016、2019、2021、2024 版软件
提供简约、高效，且可自定义的图形界面，提升部署效率。

包含了常用的办公组件，如Word、Excel、PowerPoint、OneNote、OneDrive、Outlook、Access、Visio、Project、Publisher、Lync/Skype等11大组件（自行选择添加安装即可）


自己安装发货方式：
店铺已开通自动发货，拍下后自动发送链接至聊天窗口 百度夸克双网盘发货

注意这个不是激活码，也不是序列号，也不是密钥，也不是账号。看清楚再拍。而是软件安装，安装新的永久激活版本的office及组件

安装完成后提供激活，无二次收费，一次购买，永久使用


只支持windows10版本或者windows11版本系统使用


标价就是卖价，需要请直接购买。"""

prompt = f"""You are a senior Chinese e-commerce product cover designer specializing in high-conversion marketplace listings (Xianyu / Taobao / digital software products).

Your task is to generate a HIGH-IMPACT product thumbnail, not a poster and not a UI design.

--------------------------------------------------

INPUT

Product Title:
{title}

Product Description:
{content}

Current Year:
2026

--------------------------------------------------

GOAL

Create a Chinese marketplace-style product cover with strong click-through appeal.

The image must look like a top-performing Xianyu/Taobao listing.

It must NOT look like a modern graphic design poster.

--------------------------------------------------

CRITICAL DESIGN PRINCIPLE

The design must prioritize VISUAL IMPACT over aesthetics.

The goal is:

Instant recognition + strong attention capture in thumbnail view.

--------------------------------------------------

HERO ELEMENT RULE (VERY IMPORTANT)

The cover MUST contain a dominant visual anchor.

This anchor must be one of:

- Software icons (must be LARGE and CLEAR)
- Version number (e.g., 2026, 2025) as a visual explosion element
- Application suite icons (Adobe / Office style grid)
- Device mockup (computer / screen)
- Product badge or logo

RULES:

- The hero element must be the MOST visually prominent object
- It must be significantly larger than surrounding elements
- It should be isolated in a clear visual block or card
- It should have strong contrast and separation from background
- It must NOT be small or decorative

--------------------------------------------------

TITLE RULE

Extract main title from product title.

- Must be large and bold
- Maximum 2 lines
- Must NOT compete with hero element
- Should support, not dominate

--------------------------------------------------

VERSION / NUMBER RULE (VERY IMPORTANT)

If the product contains a version (e.g. 2026 / 2024):

- The number MUST be a visual explosion element
- It should be enlarged and stylized
- It should be part of the hero hierarchy

--------------------------------------------------

SOFTWARE ICON RULE (CRITICAL FIX)

All software icons MUST:

- Be clearly visible
- Be individually separated (not blended)
- Use card/grid style layout
- Have strong contrast
- Have slight glow or highlight
- NOT be small or decorative

Icons should feel like:

"product system showcase" rather than decoration.

--------------------------------------------------

SELLING POINT RULE

Extract ONLY up to 3 key selling points.

Each must be short (less than or equal to 6 Chinese characters):

Examples:

自动安装
永久使用
极速发货
官方正版
稳定运行

Do NOT use paragraphs.

--------------------------------------------------

VISUAL STRUCTURE

The layout MUST follow:

1. Hero element (largest visual focus)
2. Secondary title (large text)
3. Icon/module system (software icons etc.)
4. Supporting badges (selling points)

The composition should feel:

Layered, modular, and commercial.

NOT symmetrical.

NOT flat.

NOT minimalist.

--------------------------------------------------

STYLE DIRECTION

Use Chinese e-commerce "high conversion listing style":

- Bold
- High contrast
- Strong hierarchy
- Dense but controlled information
- Modular layout
- Commercial advertisement feel

NOT:

- UI design
- Poster art
- Minimalism
- Corporate branding style

--------------------------------------------------

COLOR & STYLE

Automatically choose best colors based on product category.

No fixed palette.

But must ensure:

- strong contrast
- clear readability
- high saturation accents
- layered depth

--------------------------------------------------

STRICT FORBIDDEN RULES

- No store names
- No marketplace UI headers
- No platform branding
- No screenshot-like layout
- No flat icon arrangement
- No equal-weight elements
- No low-contrast design
- No decorative-only icons

--------------------------------------------------

FINAL OUTPUT

A high-conversion Chinese marketplace product cover image.

Must look like a top-performing Xianyu/Taobao software listing thumbnail with strong visual hierarchy and strong click appeal.
"""

payload = {
    "model": "gemini-3.1-flash-image",
    "messages": [
        {"role": "user", "content": prompt}
    ],
    "modalities": ["text", "image"],
    "stream": False
}

body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

req = urllib.request.Request(
    "https://x1.ninijoker-api.com/v1/chat/completions",
    data=body,
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-LBXvMHYDNumoSBN5HFLetcmeUgCkYFArtZHpKoyfDBBHFhcb",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("SUCCESS")

        content_str = data["choices"][0]["message"]["content"]
        print(f"Content type: {type(content_str).__name__}")
        print(f"Content length: {len(content_str)}")

        match = re.search(r'data:image/jpeg;base64,([A-Za-z0-9+/=]+)', content_str)
        if match:
            b64 = match.group(1)
            img_bytes = base64.b64decode(b64)

            upload_dir = r"G:\源码\xianyu-assistant-package-temp\apps\automation-service\uploads\images"
            os.makedirs(upload_dir, exist_ok=True)

            ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"gemini_test_office_v2_{ts}.jpg"
            filepath = os.path.join(upload_dir, filename)

            with open(filepath, "wb") as f:
                f.write(img_bytes)

            size = os.path.getsize(filepath)
            print(f"Image saved to: {filepath}")
            print(f"File size: {size} bytes")
            print(f"Image URL: http://localhost:12401/uploads/images/{filename}")
        else:
            print("No base64 image found in content")
            print(f"Content preview: {content_str[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(e.read().decode("utf-8"))
except Exception as e:
    print(f"Error: {e}")
