import playwright from '../apps/crawler-service/node_modules/playwright/index.js'
import fs from 'node:fs/promises'
import path from 'node:path'

const { chromium } = playwright
const root = process.cwd()
const outDir = path.join(root, 'output', 'douyin-share-video')

const inputs = [
  {
    label: '商品管理',
    path: 'C:/Users/admin/AppData/Local/Temp/codex-clipboard-ff441116-f2b6-4a6c-95ee-88a344697ab8.png',
  },
  {
    label: '商机发掘',
    path: 'C:/Users/admin/AppData/Local/Temp/codex-clipboard-fd7a717e-0120-4d99-b261-576cbc02d1e7.png',
  },
  {
    label: '在线消息',
    path: 'C:/Users/admin/AppData/Local/Temp/codex-clipboard-f5b0f18c-ff15-43d9-80fa-44c7ff649811.png',
  },
  {
    label: '工作流',
    path: 'C:/Users/admin/AppData/Local/Temp/codex-clipboard-a4175192-8b13-4150-a22c-3a3115bc99c2.png',
  },
]

const scriptMarkdown = `# 抖音短视频脚本：XianYuAssistant 项目分享

定位：项目分享种草，不做硬广，不承诺收益。
风格：芒格式反向思考，少形容词，多判断。
时长：约 29 秒。

## 口播稿

0.0-3.0 秒
反过来想，做闲鱼最容易输在哪？不是工具少，是重复动作太多，判断被打断。

3.0-8.5 秒
第一个错误，是咨询来了，人却不在。这个项目把 24 小时 AI 客服放进在线消息里，常见问题先交给规则和知识库。

8.5-14.5 秒
第二个错误，是选品只凭感觉。商机发掘可以按关键词采集商品，也能获取指定店铺商品，先看市场，再决定要不要跟。

14.5-20.5 秒
第三个错误，是每次发布都从零开始。工作流把商品获取、筛选、润色、生图、发布串成一条线。

20.5-25.8 秒
最后看控制面板：商品、自动发货、自动回复，都能集中管理。系统清楚，人就不用一直救火。

25.8-29.0 秒
我喜欢它不是因为它神奇，而是因为它把重复动作系统化，把关键判断留给人。

## 屏幕字幕

- 反过来想：闲鱼运营先少犯三个错
- 24小时 AI 客服：少漏消息
- 商机发掘：采集商品 / 指定店铺商品
- 工作流：自动发布商品
- 重复动作交给系统，关键判断留给人
`

function escapeForScript(value) {
  return value.replace(/\\/g, '\\\\').replace(/`/g, '\\`').replace(/\$/g, '\\$')
}

async function asDataUrl(filePath) {
  const buffer = await fs.readFile(filePath)
  return `data:image/png;base64,${buffer.toString('base64')}`
}

async function main() {
  await fs.mkdir(outDir, { recursive: true })

  const images = []
  for (const input of inputs) {
    images.push({
      label: input.label,
      dataUrl: await asDataUrl(input.path),
    })
  }

  const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>XianYuAssistant Douyin Share Video</title>
  <style>
    html, body {
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #edf3f8;
    }

    canvas {
      width: 1080px;
      height: 1920px;
      display: block;
    }
  </style>
</head>
<body>
  <canvas id="stage" width="1080" height="1920"></canvas>
  <script type="module">
    const imagePayload = JSON.parse(\`${escapeForScript(JSON.stringify(images))}\`);
    const canvas = document.getElementById('stage');
    const ctx = canvas.getContext('2d');
    const W = canvas.width;
    const H = canvas.height;
    const DURATION = 29;

    const palette = {
      ink: '#16233f',
      muted: '#53657f',
      blue: '#1674ff',
      green: '#138f68',
      amber: '#b56a17',
      line: 'rgba(80, 105, 143, 0.18)',
      paper: 'rgba(255, 255, 255, 0.92)',
    };

    function loadImage(src) {
      return new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => resolve(image);
        image.onerror = reject;
        image.src = src;
      });
    }

    const images = await Promise.all(imagePayload.map((item) => loadImage(item.dataUrl)));

    const scenes = [
      {
        start: 0,
        end: 3.1,
        image: 3,
        cropA: { x: 460, y: 120, w: 1240, h: 720 },
        cropB: { x: 610, y: 120, w: 1240, h: 720 },
        accent: '#1674ff',
        warm: '#18a873',
        label: '项目分享 / XianYuAssistant',
        eyebrow: '芒格式反过来想',
        title: ['闲鱼运营', '先少犯三个错'],
        body: '不是工具少，是重复动作太多，判断被打断。',
        chips: ['少漏消息', '少凭感觉', '少重复发布'],
      },
      {
        start: 3.1,
        end: 8.6,
        image: 2,
        cropA: { x: 500, y: 80, w: 1280, h: 790 },
        cropB: { x: 620, y: 120, w: 1280, h: 790 },
        accent: '#1674ff',
        warm: '#1b9e77',
        label: '01 / 在线消息',
        eyebrow: '错一：咨询来了，人却不在',
        title: ['24小时 AI 客服', '先接住常见问题'],
        body: '自动回复状态可见，规则和知识库先处理高频咨询。',
        chips: ['在线消息', 'AI 自动回复', '状态可见'],
      },
      {
        start: 8.6,
        end: 14.6,
        image: 1,
        cropA: { x: 240, y: 80, w: 1420, h: 760 },
        cropB: { x: 420, y: 120, w: 1420, h: 760 },
        accent: '#0f7f75',
        warm: '#c46b22',
        label: '02 / 商机发掘',
        eyebrow: '错二：选品只凭感觉',
        title: ['采集商品', '也看指定店铺'],
        body: '关键词搜索、店铺商品获取，先看市场，再决定动作。',
        chips: ['关键词搜索', '商品采集', '店铺商品'],
      },
      {
        start: 14.6,
        end: 20.6,
        image: 3,
        cropA: { x: 500, y: 170, w: 1250, h: 700 },
        cropB: { x: 640, y: 170, w: 1250, h: 700 },
        accent: '#246bff',
        warm: '#17a06b',
        label: '03 / 工作流',
        eyebrow: '错三：每次发布都从零开始',
        title: ['工作流', '自动发布商品'],
        body: '商品获取、筛选、润色、生图、发布，串成一条流程。',
        chips: ['商品获取', '筛选润色', '自动发布'],
      },
      {
        start: 20.6,
        end: 25.8,
        image: 0,
        cropA: { x: 230, y: 80, w: 1420, h: 780 },
        cropB: { x: 420, y: 90, w: 1420, h: 780 },
        accent: '#1674ff',
        warm: '#dd6b20',
        label: '04 / 商品管理',
        eyebrow: '最后看一件事：控制面板是否清楚',
        title: ['商品、发货、回复', '集中管理'],
        body: '自动发货与自动回复开关集中可见，人不用一直救火。',
        chips: ['商品管理', '自动发货', '自动回复'],
      },
      {
        start: 25.8,
        end: 29,
        image: 3,
        cropA: { x: 560, y: 130, w: 1220, h: 760 },
        cropB: { x: 660, y: 130, w: 1220, h: 760 },
        accent: '#0f7f75',
        warm: '#1674ff',
        label: '项目笔记',
        eyebrow: '我喜欢它的原因，不是炫技',
        title: ['重复动作交给系统', '关键判断留给人'],
        body: '这更像一个运营秩序项目，而不是一堆按钮。',
        chips: ['24小时AI客服', '商机发掘', '工作流发布'],
      },
    ];

    function clamp(n, min = 0, max = 1) {
      return Math.min(max, Math.max(min, n));
    }

    function lerp(a, b, t) {
      return a + (b - a) * t;
    }

    function easeOutCubic(t) {
      return 1 - Math.pow(1 - clamp(t), 3);
    }

    function easeInOut(t) {
      t = clamp(t);
      return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }

    function roundedRect(x, y, w, h, r) {
      const rr = Math.min(r, w / 2, h / 2);
      ctx.beginPath();
      ctx.moveTo(x + rr, y);
      ctx.arcTo(x + w, y, x + w, y + h, rr);
      ctx.arcTo(x + w, y + h, x, y + h, rr);
      ctx.arcTo(x, y + h, x, y, rr);
      ctx.arcTo(x, y, x + w, y, rr);
      ctx.closePath();
    }

    function fillRounded(x, y, w, h, r, fill) {
      roundedRect(x, y, w, h, r);
      ctx.fillStyle = fill;
      ctx.fill();
    }

    function strokeRounded(x, y, w, h, r, stroke, lineWidth = 2) {
      roundedRect(x, y, w, h, r);
      ctx.strokeStyle = stroke;
      ctx.lineWidth = lineWidth;
      ctx.stroke();
    }

    function drawBackground(scene, p) {
      const gradient = ctx.createLinearGradient(0, 0, W, H);
      gradient.addColorStop(0, '#f8fbff');
      gradient.addColorStop(0.52, '#edf5f2');
      gradient.addColorStop(1, '#fff7ed');
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, W, H);

      ctx.save();
      ctx.globalAlpha = 0.52;
      ctx.strokeStyle = 'rgba(23, 47, 79, 0.055)';
      ctx.lineWidth = 1;
      for (let x = -60; x < W + 80; x += 54) {
        ctx.beginPath();
        ctx.moveTo(x + p * 16, 0);
        ctx.lineTo(x + p * 16, H);
        ctx.stroke();
      }
      for (let y = -60; y < H + 80; y += 54) {
        ctx.beginPath();
        ctx.moveTo(0, y - p * 10);
        ctx.lineTo(W, y - p * 10);
        ctx.stroke();
      }
      ctx.restore();

      ctx.save();
      ctx.globalAlpha = 0.22;
      ctx.fillStyle = scene.accent;
      ctx.translate(W * 0.76, 92);
      ctx.rotate(-0.12);
      fillRounded(0, 0, 350, 76, 38, scene.accent);
      ctx.restore();

      ctx.save();
      ctx.globalAlpha = 0.15;
      ctx.fillStyle = scene.warm;
      ctx.translate(-70, 1510);
      ctx.rotate(-0.26);
      fillRounded(0, 0, 500, 110, 55, scene.warm);
      ctx.restore();
    }

    function drawPill(text, x, y, color) {
      ctx.font = '700 25px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      const width = ctx.measureText(text).width + 44;
      fillRounded(x, y, width, 52, 26, 'rgba(255, 255, 255, 0.86)');
      strokeRounded(x, y, width, 52, 26, 'rgba(61, 84, 122, 0.12)', 1.5);
      ctx.fillStyle = color;
      ctx.fillText(text, x + 22, y + 35);
    }

    function drawTitle(lines, x, y) {
      ctx.fillStyle = palette.ink;
      ctx.font = '900 70px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      ctx.textBaseline = 'top';
      lines.forEach((line, index) => {
        ctx.fillText(line, x, y + index * 86);
      });
    }

    function drawBody(text, x, y, maxWidth) {
      ctx.fillStyle = palette.muted;
      ctx.font = '500 34px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      ctx.textBaseline = 'top';
      const words = Array.from(text);
      let line = '';
      let currentY = y;
      for (const word of words) {
        const test = line + word;
        if (ctx.measureText(test).width > maxWidth && line) {
          ctx.fillText(line, x, currentY);
          line = word;
          currentY += 50;
        } else {
          line = test;
        }
      }
      if (line) ctx.fillText(line, x, currentY);
    }

    function drawChips(chips, x, y, scene) {
      let nextX = x;
      ctx.font = '700 27px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      for (const chip of chips) {
        const width = ctx.measureText(chip).width + 42;
        fillRounded(nextX, y, width, 50, 25, 'rgba(255, 255, 255, 0.82)');
        strokeRounded(nextX, y, width, 50, 25, 'rgba(61, 84, 122, 0.13)', 1.5);
        ctx.fillStyle = nextX === x ? scene.accent : palette.ink;
        ctx.fillText(chip, nextX + 21, y + 34);
        nextX += width + 14;
      }
    }

    function drawScreenshot(scene, p) {
      const image = images[scene.image];
      const cardX = 64;
      const cardY = 650;
      const cardW = 952;
      const cardH = 835;
      const entrance = easeOutCubic(Math.min(p / 0.24, 1));
      const y = cardY + (1 - entrance) * 60;
      const zoom = 1 + Math.sin(p * Math.PI) * 0.025;

      ctx.save();
      ctx.shadowColor = 'rgba(31, 53, 94, 0.18)';
      ctx.shadowBlur = 42;
      ctx.shadowOffsetY = 22;
      fillRounded(cardX, y, cardW, cardH, 34, 'rgba(255, 255, 255, 0.96)');
      ctx.restore();

      fillRounded(cardX + 18, y + 18, cardW - 36, 64, 24, '#f4f8fd');
      ctx.fillStyle = '#e55353';
      ctx.beginPath();
      ctx.arc(cardX + 54, y + 50, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#f2b84b';
      ctx.beginPath();
      ctx.arc(cardX + 84, y + 50, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#30ad73';
      ctx.beginPath();
      ctx.arc(cardX + 114, y + 50, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#62748f';
      ctx.font = '700 24px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      ctx.fillText(imagePayload[scene.image].label, cardX + 148, y + 58);

      const imageX = cardX + 18;
      const imageY = y + 96;
      const imageW = cardW - 36;
      const imageH = cardH - 118;

      const crop = {
        x: lerp(scene.cropA.x, scene.cropB.x, easeInOut(p)),
        y: lerp(scene.cropA.y, scene.cropB.y, easeInOut(p)),
        w: lerp(scene.cropA.w, scene.cropB.w, easeInOut(p)) / zoom,
        h: lerp(scene.cropA.h, scene.cropB.h, easeInOut(p)) / zoom,
      };

      ctx.save();
      roundedRect(imageX, imageY, imageW, imageH, 24);
      ctx.clip();
      ctx.drawImage(image, crop.x, crop.y, crop.w, crop.h, imageX, imageY, imageW, imageH);
      const shine = ctx.createLinearGradient(imageX, imageY, imageX + imageW, imageY + imageH);
      shine.addColorStop(0, 'rgba(255,255,255,0.0)');
      shine.addColorStop(0.5, 'rgba(255,255,255,0.10)');
      shine.addColorStop(1, 'rgba(255,255,255,0.0)');
      ctx.fillStyle = shine;
      ctx.fillRect(imageX, imageY, imageW, imageH);
      ctx.restore();

      strokeRounded(cardX, y, cardW, cardH, 34, 'rgba(39, 91, 161, 0.14)', 2);
    }

    function drawQuote(scene, p) {
      const x = 72;
      const y = 1518;
      fillRounded(x, y, 936, 208, 32, 'rgba(255, 255, 255, 0.78)');
      strokeRounded(x, y, 936, 208, 32, 'rgba(61, 84, 122, 0.12)', 1.5);
      ctx.fillStyle = scene.accent;
      ctx.font = '900 30px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      ctx.fillText('项目观察', x + 38, y + 56);
      ctx.fillStyle = palette.ink;
      ctx.font = '800 39px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      const summary = p > 0.78
        ? '把重复动作系统化，把关键判断留给人。'
        : '先问：它减少了哪类错误？';
      drawBody(summary, x + 38, y + 86, 820);
    }

    function drawProgress(t) {
      const x = 72;
      const y = 1816;
      const w = 936;
      fillRounded(x, y, w, 10, 5, 'rgba(40, 57, 88, 0.12)');
      fillRounded(x, y, w * clamp(t / DURATION), 10, 5, '#16233f');
      ctx.fillStyle = '#66748a';
      ctx.font = '600 24px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('非广告向项目分享', W / 2, 1870);
      ctx.textAlign = 'left';
    }

    function draw(t) {
      const scene = scenes.find((item) => t >= item.start && t < item.end) || scenes[scenes.length - 1];
      const p = clamp((t - scene.start) / (scene.end - scene.start));
      const fadeIn = clamp(p / 0.16);
      const fadeOut = clamp((1 - p) / 0.16);
      const alpha = Math.min(fadeIn, fadeOut);

      drawBackground(scene, p);

      ctx.save();
      ctx.globalAlpha = alpha;
      drawPill(scene.label, 72, 82, scene.accent);

      ctx.fillStyle = scene.warm;
      ctx.font = '900 31px "Noto Sans SC", "Microsoft YaHei", sans-serif';
      ctx.textBaseline = 'top';
      ctx.fillText(scene.eyebrow, 72, 172);

      drawTitle(scene.title, 72, 226);
      drawBody(scene.body, 72, 422, 900);
      drawChips(scene.chips, 72, 545, scene);
      drawScreenshot(scene, p);
      drawQuote(scene, p);
      ctx.restore();

      drawProgress(t);
    }

    window.renderAt = (time) => draw(time);

    window.recordVideo = async () => {
      const mimeTypes = [
        'video/webm;codecs=vp9',
        'video/webm;codecs=vp8',
        'video/webm',
      ];
      const mimeType = mimeTypes.find((type) => MediaRecorder.isTypeSupported(type)) || '';
      const stream = canvas.captureStream(30);
      const recorder = new MediaRecorder(stream, {
        mimeType,
        videoBitsPerSecond: 4_000_000,
      });
      const chunks = [];
      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size) chunks.push(event.data);
      };
      const stopped = new Promise((resolve) => {
        recorder.onstop = resolve;
      });

      await document.fonts.ready;
      recorder.start(250);
      const startedAt = performance.now();

      await new Promise((resolve) => {
        function tick(now) {
          const t = Math.min((now - startedAt) / 1000, DURATION);
          draw(t);
          if (t < DURATION) {
            requestAnimationFrame(tick);
          } else {
            resolve();
          }
        }
        requestAnimationFrame(tick);
      });

      recorder.stop();
      await stopped;

      const blob = new Blob(chunks, { type: mimeType || 'video/webm' });
      const bytes = new Uint8Array(await blob.arrayBuffer());
      let binary = '';
      const chunkSize = 0x8000;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
      }
      return btoa(binary);
    };

    draw(0);
  </script>
</body>
</html>`

  const htmlPath = path.join(outDir, 'douyin-share-video.html')
  const videoPath = path.join(outDir, 'xianyuassistant-douyin-share.webm')
  const previewPath = path.join(outDir, 'preview.png')
  const scriptPath = path.join(outDir, 'douyin-share-script.md')

  await fs.writeFile(htmlPath, html, 'utf8')
  await fs.writeFile(scriptPath, scriptMarkdown, 'utf8')

  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 })
  await page.goto(`file:///${htmlPath.replace(/\\/g, '/')}`)
  await page.waitForFunction(() => typeof window.renderAt === 'function' && typeof window.recordVideo === 'function')
  await page.evaluate(() => window.renderAt(9.5))
  await page.locator('canvas').screenshot({ path: previewPath })
  const base64 = await page.evaluate(() => window.recordVideo())
  await browser.close()

  await fs.writeFile(videoPath, Buffer.from(base64, 'base64'))

  console.log(JSON.stringify({
    outDir,
    htmlPath,
    videoPath,
    previewPath,
    scriptPath,
  }, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
