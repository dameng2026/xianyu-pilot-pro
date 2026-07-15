$title = "Adobe全家桶2026版｜PS/PR/AE/AI/PDF全都有 拍一发全套软件，永久免费用，不用激活，直接一键安装，超方便～"
$content = "Adobe全家桶2026版｜PS/PR/AE/AI/PDF全都有 拍一发全套软件，永久免费用，不用激活，直接一键安装，超方便～ MAC全系统都能装，intel/M1/M2/M3/M4都支持，Win7只支持到18年，Win10/11全都能用 去年到今年的版本都有，2017-2026都能选，想用哪个版本直接挑就行 自动发货，下单秒发，不限速，下载很快，带安装教程，小白也能轻松搞定 还有远程安装服务，不会操作或者懒得折腾的可以直接找我，帮你装好就能用，省心省力 价格真的很划算，懂的都懂，需要的直接拍，细节可以私聊问我～"

$prompt = @"
# ROLE

You are a professional designer specializing in high-conversion product covers for Chinese e-commerce platforms (Xianyu, Taobao, Pinduoduo).

Your task is NOT to create an artistic poster.

Your task is to create a commercial product thumbnail with strong visual impact and high click-through rate.

The design language should resemble successful Chinese marketplace product covers instead of modern minimalist posters.

--------------------------------------------------

# INPUT

Product Title

$title

Product Description

$content

--------------------------------------------------

# TASK

Read the title and description.

Understand what the product is.

Automatically extract the most important selling points.

Create a professional Chinese e-commerce product cover.

The cover should immediately tell users what the product is while being visually attractive.

--------------------------------------------------

# DESIGN STYLE

Use the visual language commonly found in successful Chinese marketplace product covers.

The overall style should be

commercial

bold

eye-catching

information-focused

high contrast

rich visual hierarchy

professional

premium

not minimalist.

The cover should feel like a best-selling Xianyu or Taobao digital product listing.

--------------------------------------------------

# LAYOUT

The layout must have ONE dominant visual focus.

Never distribute information evenly.

Visual priority should follow:

(1) Hero Element

Largest object in the composition.

Can be:

software logo

application icon

device mockup

software interface

product illustration

version number

brand logo

or other product-related visual.

The hero element should occupy approximately 35 percent to 50 percent of the overall visual weight.

--------------------------------------------------

(2) Main Title

Generate from Product Title.

Maximum 2 lines.

Very large bold typography.

Easy to read in thumbnail size.

Placed close to the hero element.

--------------------------------------------------

(3) Selling Points

Extract automatically from Product Description.

Display only the three most important selling points.

Each selling point should contain no more than 6 Chinese characters.

Examples:

永久更新

官方正版

极速发货

自动安装

稳定运行

终身售后

高速下载

远程安装

One-click activation

Never display paragraphs.

--------------------------------------------------

(4) Compatibility / Version

If applicable,

extract only important compatibility information.

Examples:

Win / Mac

Office 2024

Adobe 2025

M1 M2 M3

FCPX 10.6+

Windows 11

Display as a small supporting module.

--------------------------------------------------

# PRODUCT VISUALIZATION

Whenever possible,

generate a realistic product representation.

Examples:

Software

software icons

Adobe suite

Adobe application icon grid

Office

Word Excel PowerPoint icons

Plugin

software interface

Membership

application logo

AI tools

modern software dashboard

Operating system

computer mockup

Digital products

related visual object

The product visual should become the primary visual anchor.

Avoid text-only compositions.

--------------------------------------------------

# COMPOSITION

Create a dynamic composition.

Avoid perfect symmetry.

Allow overlapping elements.

Allow layered design.

Allow cards, labels, ribbons and badges.

Create depth through layout rather than excessive visual effects.

Keep the design energetic and commercial.

--------------------------------------------------

# COLORS

Automatically choose the most suitable

background

colors

typography

decorations

lighting

according to the product category.

No fixed color palette is required.

--------------------------------------------------

# TYPOGRAPHY

Chinese typography should be bold and highly readable.

Important information must be significantly larger than secondary information.

Large numbers and keywords may be emphasized.

The hierarchy should be obvious even when viewed as a small thumbnail.

--------------------------------------------------

# DECORATIONS

Use only necessary decorative elements.

Simple geometric shapes

labels

badges

icons

cards

light glow

gradient

depth

All decorative elements should reinforce readability.

--------------------------------------------------

# STRICT RULES

Never generate a flyer.

Never generate an instruction page.

Never generate a product detail page.

Never generate paragraphs.

Never display dense text.

Never use more than three selling points.

Never make every element the same size.

Never create multiple competing visual centers.

Never overload the design with unnecessary decorations.

Do not imitate presentation slides.

Do not imitate modern minimalist graphic posters.

--------------------------------------------------

# FINAL GOAL

Generate a premium Chinese e-commerce product cover.

The result should resemble a high-performing Xianyu or Taobao product thumbnail.

It should look commercially designed, highly clickable, visually rich, easy to understand, and optimized for thumbnail browsing rather than artistic presentation.
"@

$body = @{
    model = "gemini-3.1-flash-image"
    messages = @(
        @{
            role = "user"
            content = $prompt
        }
    )
    modalities = @("text", "image")
    stream = $false
} | ConvertTo-Json -Depth 10

$headers = @{
    "Content-Type" = "application/json"
    "Authorization" = "Bearer sk-LBXvMHYDNumoSBN5HFLetcmeUgCkYFArtZHpKoyfDBBHFhcb"
}

try {
    $response = Invoke-RestMethod -Uri "https://x1.ninijoker-api.com/v1/chat/completions" -Method POST -Headers $headers -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -TimeoutSec 180
    Write-Host "SUCCESS"

    $content = $response.choices[0].message.content
    Write-Host "Content type: $($content.GetType().Name)"
    Write-Host "Content length: $($content.Length)"

    if ($content -match 'data:image/jpeg;base64,([A-Za-z0-9+/=]+)') {
        $base64Data = $matches[1]
        $imageBytes = [System.Convert]::FromBase64String($base64Data)

        $uploadDir = "G:\源码\xianyu-assistant-package-temp\apps\automation-service\uploads\images"
        if (-not (Test-Path $uploadDir)) {
            New-Item -ItemType Directory -Path $uploadDir -Force
        }

        $fileName = "gemini_test_v3_$(Get-Date -Format 'yyyyMMddHHmmss').jpg"
        $filePath = Join-Path $uploadDir $fileName
        [System.IO.File]::WriteAllBytes($filePath, $imageBytes)

        Write-Host "Image saved to: $filePath"
        Write-Host "File size: $((Get-Item $filePath).Length) bytes"
        Write-Host "Image URL: http://localhost:12401/uploads/images/$fileName"
    } else {
        Write-Host "No base64 image found in content"
        Write-Host "Content preview: $($content.Substring(0, [Math]::Min(500, $content.Length)))"
    }
} catch {
    Write-Host "Error: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body: $responseBody"
    }
}
