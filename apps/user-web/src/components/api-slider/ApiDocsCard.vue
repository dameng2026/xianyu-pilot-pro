<template>
  <CardPanel title="API 对接文档" desc="按以下步骤对接您的系统">
    <!-- 1. 接入步骤 -->
    <div class="steps">
      <div class="step" v-for="(s, i) in steps" :key="i">
        <div class="step-num">{{ i + 1 }}</div>
        <div class="step-name">{{ s }}</div>
        <div class="step-arrow" v-if="i < steps.length - 1">→</div>
      </div>
    </div>

    <!-- 2. 求解流程 -->
    <div class="flow">
      <div class="flow-node" v-for="(f, i) in flow" :key="i">
        <div class="flow-icon" :class="{ 'flow-done': i === flow.length - 1 }">{{ i === flow.length - 1 ? '✓' : '○' }}</div>
        <div class="flow-name">{{ f }}</div>
        <div class="flow-line" v-if="i < flow.length - 1"></div>
      </div>
    </div>

    <!-- 3. 请求参数 -->
    <h4 class="section-title">请求参数</h4>
    <table class="param-table">
      <thead>
        <tr><th>参数名</th><th>类型</th><th>必填</th><th>说明</th></tr>
      </thead>
      <tbody>
        <tr><td>X-Api-Key</td><td>string（Header）</td><td>是</td><td>对接密钥，可在本页「对接密钥」卡片获取</td></tr>
        <tr><td>cookie</td><td>string（Body）</td><td>是</td><td>闲鱼完整 Cookie</td></tr>
      </tbody>
    </table>
    <p class="param-tip">仅需提交对接密钥与完整 Cookie 即可，无需填写目标页面 URL 与超时时间，系统会自动处理。</p>

    <!-- 4. 返回参数 -->
    <h4 class="section-title">返回参数</h4>
    <div class="param-tags">
      <span class="param-tag" v-for="p in responseParams" :key="p.name">
        <b>{{ p.name }}</b>：{{ p.desc }}
      </span>
    </div>

    <!-- 5. 请求响应示例 -->
    <h4 class="section-title">请求与响应示例</h4>
    <div class="code-blocks">
      <div class="code-card">
        <div class="code-card-header">
          <span class="code-card-lang">Shell / cURL</span>
          <button class="code-copy-btn" @click="copyCode(requestExample, $event)">复制</button>
        </div>
        <pre class="code-card-body"><code>{{ requestExample }}</code></pre>
      </div>
      <div class="code-card">
        <div class="code-card-header">
          <span class="code-card-lang">JSON</span>
          <button class="code-copy-btn" @click="copyCode(responseExample, $event)">复制</button>
        </div>
        <pre class="code-card-body"><code>{{ responseExample }}</code></pre>
      </div>
    </div>

    <!-- 6. 对接代码示例 -->
    <h4 class="section-title">对接代码示例</h4>
    <p class="param-tip">以下示例展示如何向本平台发起滑块求解请求、接收并处理响应。请将 <code>YOUR_API_KEY</code> 替换为本页「对接密钥」卡片中的密钥；实际扣费由接口按当前动态价格返回，请以页面显示价格和响应字段为准。</p>
    <div class="code-tabs">
      <button
        v-for="t in codeTabs"
        :key="t.key"
        :class="['code-tab', { active: activeCodeTab === t.key }]"
        @click="activeCodeTab = t.key"
      >{{ t.label }}</button>
    </div>
    <div class="code-card">
      <div class="code-card-header">
        <span class="code-card-lang">{{ activeCodeMeta.title }}</span>
        <button class="code-copy-btn" @click="copyCode(activeCodeMeta.code, $event)">复制</button>
      </div>
      <pre class="code-card-body"><code>{{ activeCodeMeta.code }}</code></pre>
    </div>

    <!-- 7. 开源版说明 -->
    <div class="opensource-note">
      <h5>接入开源版说明</h5>
      <ol>
        <li>在商业版「API滑块求解」页面获取 apiKey</li>
        <li>在开源版「设置 → 商业版 API 对接」填入 apiKey 与 API 地址</li>
        <li>开源版触发滑块时自动调用商业版 API，成功后按规则扣 Token</li>
      </ol>
    </div>
  </CardPanel>
</template>

<script setup>
import { ref, computed } from 'vue'
import CardPanel from '../CardPanel.vue'

// 复制代码到剪贴板，复制成功后按钮文案短暂变为「已复制」
function copyCode(text, evt) {
  if (!text) return
  const btn = evt?.currentTarget
  const restore = () => {
    if (btn) { btn.textContent = '复制'; btn.classList.remove('copied') }
  }
  const ok = () => {
    if (btn) { btn.textContent = '已复制'; btn.classList.add('copied') }
    setTimeout(restore, 1600)
  }
  const fail = () => {
    if (btn) { btn.textContent = '复制失败'; btn.classList.add('copied') }
    setTimeout(restore, 1600)
  }
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(ok).catch(fail)
  } else {
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      ok()
    } catch { fail() }
  }
}

const steps = ['提交密钥与 Cookie', '预检测', '执行求解', '返回结果']
const flow = ['识别滑块场景', '预检测是否可求解', '调用滑块求解能力', '返回求解结果与日志', '成功后计费']

const responseParams = [
  { name: 'ok', desc: 'boolean 是否成功' },
  { name: 'status', desc: 'success/fail/timeout/precheck_rejected/service_unavailable' },
  { name: 'solved', desc: 'boolean 滑块是否通过' },
  { name: 'captchaDetected', desc: 'boolean 是否检测到滑块' },
  { name: 'attempts', desc: 'number 拖动次数' },
  { name: 'durationMs', desc: 'number 耗时毫秒' },
  { name: 'cookies', desc: 'string 新鲜 Cookie（仅成功）' },
  { name: 'error', desc: 'string 失败原因（脱敏）' },
  { name: 'recordId', desc: 'string 请求唯一 ID' },
  { name: 'tokenCharged', desc: 'number 实际扣费 Token 数，以接口返回为准' },
]

const requestExample = `curl -X POST https://api.xianyupilot.com/api/v1/slider/solve \\
  -H "X-Api-Key: YOUR_API_KEY" \\
  -H "Content-Type: application/json" \\
  -d '{
    "cookie": "您的闲鱼完整Cookie"
  }'`

const responseExample = `{
  "ok": true,
  "status": "success",
  "solved": true,
  "captchaDetected": true,
  "attempts": 3,
  "durationMs": 5200,
  "cookies": "求解后的新鲜Cookie",
  "recordId": "req_a1b2c3d4",
  "tokenCharged": "由接口按当前动态价格返回"
}`

const pythonCode = `# Python 对接示例
# 依赖：pip install requests
import requests

API_URL = "https://api.xianyupilot.com/api/v1/slider/solve"
API_KEY = "YOUR_API_KEY"  # 替换为本页获取的对接密钥

def solve_slider(cookie: str) -> dict:
    """向本平台发起滑块求解请求，返回求解结果。"""
    headers = {
        "X-Api-Key": API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"cookie": cookie}
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=120)
    data = resp.json()

    # 处理响应
    if data.get("ok") and data.get("solved"):
        # 求解成功，使用返回的新鲜 Cookie 继续业务
        fresh_cookie = data.get("cookies", "")
        print(f"求解成功，耗时 {data.get('durationMs')}ms，扣费 {data.get('tokenCharged')} Token")
        return {"success": True, "cookie": fresh_cookie, "record_id": data.get("recordId")}
    else:
        # 求解失败，根据 status 区分原因
        print(f"求解失败：{data.get('status')} - {data.get('error')}")
        return {"success": False, "status": data.get("status"), "error": data.get("error")}


if __name__ == "__main__":
    your_cookie = "在此填入闲鱼完整 Cookie"
    result = solve_slider(your_cookie)
    print(result)`

const phpCode = `<?php
// PHP 对接示例
// 依赖：PHP 7.4+，需启用 cURL 扩展

$API_URL = 'https://api.xianyupilot.com/api/v1/slider/solve';
$API_KEY = 'YOUR_API_KEY'; // 替换为本页获取的对接密钥

/**
 * 向本平台发起滑块求解请求，返回求解结果数组。
 */
function solveSlider(string $cookie): array {
    global $API_URL, $API_KEY;

    $payload = json_encode(['cookie' => $cookie]);

    $ch = curl_init($API_URL);
    curl_setopt_array($ch, [
        CURLOPT_POST           => true,
        CURLOPT_POSTFIELDS     => $payload,
        CURLOPT_HTTPHEADER     => [
            'X-Api-Key: ' . $API_KEY,
            'Content-Type: application/json',
        ],
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT        => 120,
    ]);

    $response = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error    = curl_error($ch);
    curl_close($ch);

    if ($error) {
        return ['success' => false, 'error' => '请求失败: ' . $error];
    }

    $data = json_decode($response, true);

    // 处理响应
    if (!empty($data['ok']) && !empty($data['solved'])) {
        // 求解成功，使用返回的新鲜 Cookie 继续业务
        return [
            'success'    => true,
            'cookie'     => $data['cookies'] ?? '',
            'record_id'  => $data['recordId'] ?? '',
            'charged'    => $data['tokenCharged'] ?? 0,
        ];
    }

    // 求解失败
    return [
        'success' => false,
        'status'  => $data['status'] ?? 'unknown',
        'error'   => $data['error'] ?? '未知错误',
    ];
}

// 使用示例
$yourCookie = '在此填入闲鱼完整 Cookie';
$result = solveSlider($yourCookie);
print_r($result);`

const jsCode = `// JavaScript / Node.js 对接示例
// 依赖：Node 18+ 内置 fetch，或安装 node-fetch

const API_URL = 'https://api.xianyupilot.com/api/v1/slider/solve';
const API_KEY = 'YOUR_API_KEY'; // 替换为本页获取的对接密钥

/**
 * 向本平台发起滑块求解请求，返回求解结果。
 * @param {string} cookie 闲鱼完整 Cookie
 */
async function solveSlider(cookie) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'X-Api-Key': API_KEY,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ cookie }),
    // 超时控制（Node 18+ 支持 AbortSignal.timeout）
    signal: AbortSignal.timeout(120000),
  });

  const data = await response.json();

  // 处理响应
  if (data.ok && data.solved) {
    // 求解成功，使用返回的新鲜 Cookie 继续业务
    return {
      success: true,
      cookie: data.cookies,
      recordId: data.recordId,
    };
  }

  // 求解失败，根据 status 区分原因
  return {
    success: false,
    status: data.status,
    error: data.error,
  };
}

// 使用示例
(async () => {
  const yourCookie = '在此填入闲鱼完整 Cookie';
  const result = await solveSlider(yourCookie);
  return result;
})();`

const codeTabs = [
  { key: 'python', label: 'Python' },
  { key: 'php', label: 'PHP' },
  { key: 'js', label: 'JavaScript / Node.js' },
]

const codeMap = {
  python: { title: 'Python 对接示例', code: pythonCode },
  php: { title: 'PHP 对接示例', code: phpCode },
  js: { title: 'JavaScript / Node.js 对接示例', code: jsCode },
}

const activeCodeTab = ref('python')
const activeCodeMeta = computed(() => codeMap[activeCodeTab.value] || codeMap.python)
</script>

<style scoped>
.steps { display: flex; align-items: center; gap: 8px; margin: 16px 0; flex-wrap: wrap; }
.step { display: flex; align-items: center; gap: 6px; }
.step-num { width: 28px; height: 28px; border-radius: 50%; background: var(--primary); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 14px; }
.step-name { font-size: 13px; color: var(--text); }
.step-arrow { color: var(--muted); }
.flow { display: flex; align-items: center; margin: 16px 0; flex-wrap: wrap; gap: 4px; }
.flow-node { display: flex; align-items: center; gap: 6px; }
.flow-icon { width: 24px; height: 24px; border-radius: 6px; background: #f0f4ff; color: var(--primary); display: flex; align-items: center; justify-content: center; font-size: 12px; }
.flow-done { background: #e8f5e9; color: var(--green); }
.flow-name { font-size: 12px; color: var(--muted); }
.flow-line { width: 20px; height: 1px; background: var(--line); }
.section-title { font-size: 15px; color: var(--text); margin: 20px 0 10px; }
.param-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.param-table th { background: #f5f8ff; color: var(--muted); padding: 8px 12px; text-align: left; border: 1px solid var(--line); font-weight: 500; }
.param-table td { padding: 8px 12px; border: 1px solid var(--line); color: var(--text); }
.param-tip { font-size: 12px; color: var(--muted); margin: 8px 0 0; line-height: 1.6; }
.param-tip code { background: #f0f4ff; color: var(--primary); padding: 1px 6px; border-radius: 4px; font-size: 12px; }
.param-tags { display: flex; flex-wrap: wrap; gap: 8px; }
.param-tag { background: #e3f2fd; color: var(--primary); padding: 4px 10px; border-radius: 6px; font-size: 12px; }
.code-blocks { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

/* 代码卡片：参考掘金/CSDN 暗色主题 */
.code-card {
  background: #1e1e1e;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #2d2d2d;
  margin-top: 4px;
}
.code-card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px;
  background: #252526;
  border-bottom: 1px solid #2d2d2d;
}
.code-card-lang {
  font-size: 12px;
  color: #9cdcfe;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-weight: 500;
}
.code-copy-btn {
  padding: 3px 10px;
  font-size: 12px;
  color: #c9cccc;
  background: #3a3d41;
  border: 1px solid #4a4d51;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s;
}
.code-copy-btn:hover { background: #4a4d51; color: #fff; }
.code-copy-btn.copied { background: #2ea043; border-color: #2ea043; color: #fff; }
.code-card-body {
  margin: 0;
  padding: 14px;
  overflow-x: auto;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #d4d4d4;
  background: #1e1e1e;
  white-space: pre;
  tab-size: 2;
}
.code-card-body code {
  font-family: inherit;
  color: inherit;
  background: transparent;
  white-space: pre;
}
/* 滚动条美化 */
.code-card-body::-webkit-scrollbar { height: 8px; width: 8px; }
.code-card-body::-webkit-scrollbar-track { background: #1e1e1e; }
.code-card-body::-webkit-scrollbar-thumb { background: #4a4d51; border-radius: 4px; }
.code-card-body::-webkit-scrollbar-thumb:hover { background: #5a5d61; }

.code-tabs { display: flex; gap: 4px; margin: 10px 0 0; border-bottom: 1px solid var(--line); }
.code-tab { padding: 8px 16px; border: none; background: transparent; cursor: pointer; font-size: 13px; color: var(--muted); border-bottom: 2px solid transparent; }
.code-tab.active { color: var(--primary); border-bottom-color: var(--primary); }
.opensource-note { margin-top: 20px; padding: 16px; background: #f0f7ff; border-radius: 8px; }
.opensource-note h5 { margin: 0 0 8px; color: var(--primary); }
.opensource-note ol { margin: 0; padding-left: 20px; color: var(--muted); font-size: 13px; }
.opensource-note li { margin: 4px 0; }
@media (max-width: 768px) {
  .code-blocks { grid-template-columns: 1fr; }
}
</style>
