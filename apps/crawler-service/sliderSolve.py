#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
闲鱼滑块验证自动求解器（Python · Playwright page.mouse，不控制用户硬件鼠标）

核心策略（基于实测与历史失败截图分析）：
1. 同页连续失败会累积 Baxia 惩罚态；每次失败后必须彻底重置（清 storage + 回首页 + 再进消息页）
2. 使用真实 Chrome + CDP，配合 page.mouse 生成 isTrusted 鼠标事件
3. 拖动：接近轨迹、起点偏移、钟形速度、Y 弧线、过冲回退；奇偶次交替容器内/出容器拖动
4. 每轮 pre/post 截图，便于视觉复盘
5. 成功后导出最新 Cookie（含 _m_h5_tk 等）
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Optional

try:
    # patchright 是 Playwright 的反检测分支，自动清理 CDP 痕迹（cdc_/__playwright__/Runtime.enable），
    # 从根本上解决 Baxia 通过 CDP 协议识别 Playwright 控制的问题。
    # API 完全兼容 Playwright，只需替换 import。
    from patchright.async_api import async_playwright
    _USING_PATCHRIGHT = True
except ImportError:
    try:
        from playwright.async_api import async_playwright
        _USING_PATCHRIGHT = False
    except ImportError:
        print("ERROR: patchright/playwright is not installed. Run: pip install patchright", file=sys.stderr)
        sys.exit(2)

WINDOW_WIDTH = 1366
WINDOW_HEIGHT = 768
DEFAULT_TARGET_URL = "https://www.goofish.com/im"
DEFAULT_MAX_RETRIES = 5

# 人工在「自动化窗口」里拖也失败的根因：环境被标为机器人（非轨迹）。
# Baxia 检测维度（2026 实测）：
#   1. navigator.webdriver / navigator.plugins instanceof / navigator.languages
#   2. window.chrome 完整性（runtime/csi/loadTimes/app）
#   3. WebGL vendor&renderer（SwiftShader = 机器人强信号）
#   4. Canvas 指纹（headless 固定哈希）
#   5. AudioContext 指纹（headless 返回固定值）
#   6. navigator.userAgentData (Client Hints) — Chrome 131+ 必有，Playwright 缺失即识破
#   7. navigator.connection (Network Information API) — 真人必有
#   8. navigator.getBattery() — 真人浏览器必有
#   9. MediaDevices.enumerateDevices — 真人有音频/视频设备
#  10. WebRTC IP 泄漏 — 暴露内网 IP 与公网 IP 不一致
#  11. window.outerWidth/outerHeight — headless 下 outerWidth==innerWidth
#  12. navigator.permissions.query 一致性
#  13. CDP 注入痕迹：cdc_ / $cdc_ / __playwright / Runtime.enable 检测
#  14. speechSynthesis.getVoices — headless 返回空数组
#  15. navigator.webdriver 通过 toString 检测（native code vs 重新定义）
# 本脚本全面覆盖以上检测点
STEALTH_INIT_SCRIPT = r"""
(() => {
  // 工具：安全定义属性，避免重复定义报错
  const defineGetter = (obj, prop, getter) => {
    try {
      Object.defineProperty(obj, prop, { get: getter, configurable: true });
    } catch (e) {}
  };

  try {
    // ===== 1. navigator.webdriver =====
    // 删除原型属性 + 重定义为 undefined，双重保险
    try { delete Object.getPrototypeOf(navigator).webdriver; } catch (e) {}
    defineGetter(navigator, 'webdriver', () => undefined);
    try {
      defineGetter(Navigator.prototype, 'webdriver', () => undefined);
    } catch (e) {}

    // ===== 2. window.chrome 完整对象 =====
    if (!window.chrome) window.chrome = {};
    if (!window.chrome.runtime) {
      window.chrome.runtime = {
        OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
        OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
        PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
        PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
        // 真人 Chrome 有 runtime.id（扩展 ID），空值也可但有的检测会查
        id: undefined,
        // connect / sendMessage 让检测脚本调用不报错
        connect: () => {},
        sendMessage: () => {},
      };
    }
    if (!window.chrome.csi) {
      window.chrome.csi = () => ({ startE: Date.now() - Math.floor(Math.random() * 3000 + 2000), onloadT: Date.now(), pageT: Math.random() * 2000 + 500, tran: 15 });
    }
    if (!window.chrome.loadTimes) {
      const t = Date.now() / 1000;
      window.chrome.loadTimes = () => ({
        commitLoadTime: t - 4,
        connectionInfo: 'h2',
        finishDocumentLoadTime: t - 2,
        finishLoadTime: t - 1.5,
        firstPaintAfterLoadTime: t - 1.8,
        firstPaintTime: t - 3,
        navigationType: 'Other',
        npnNegotiatedProtocol: 'h2',
        requestTime: t - 5,
        startLoadTime: t - 5,
        wasAlternateProtocolAvailable: false,
        wasFetchedViaSpdy: true,
        wasNpnNegotiated: true,
      });
    }
    if (!window.chrome.app) {
      window.chrome.app = { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } };
    }

    // ===== 3. navigator.plugins 真实 PluginArray 结构 =====
    const mkPlugin = (name, filename, description) => {
      const p = { name, filename, description, length: 1 };
      p[0] = { type: 'application/pdf', suffixes: 'pdf', description };
      p.item = (i) => p[i] || null;
      p.namedItem = (n) => (n === name ? p : null);
      return p;
    };
    const pluginData = [
      mkPlugin('PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      mkPlugin('Chrome PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      mkPlugin('Chromium PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      mkPlugin('Microsoft Edge PDF Viewer', 'internal-pdf-viewer', 'Portable Document Format'),
      mkPlugin('WebKit built-in PDF', 'internal-pdf-viewer', 'Portable Document Format'),
    ];
    defineGetter(navigator, 'plugins', () => {
      const arr = pluginData.slice();
      arr.length = pluginData.length;
      arr.item = (i) => arr[i] || null;
      arr.namedItem = (n) => arr.find(x => x.name === n) || null;
      arr.refresh = () => {};
      return arr;
    });
    // mimeTypes 真实结构
    defineGetter(navigator, 'mimeTypes', () => {
      const m = [{ type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format', enabledPlugin: pluginData[0] }];
      m.length = 1;
      m.item = (i) => m[i] || null;
      m.namedItem = (n) => (m[0] && m[0].type === n ? m[0] : null);
      return m;
    });

    // ===== 4. navigator 基础属性 =====
    defineGetter(navigator, 'languages', () => ['zh-CN', 'zh', 'en-US', 'en']);
    defineGetter(navigator, 'language', () => 'zh-CN');
    defineGetter(navigator, 'platform', () => 'Win32');
    defineGetter(navigator, 'hardwareConcurrency', () => 8);
    defineGetter(navigator, 'deviceMemory', () => 8);
    defineGetter(navigator, 'maxTouchPoints', () => 0);
    // navigator.vendor 必须匹配 Chrome
    defineGetter(navigator, 'vendor', () => 'Google Inc.');
    defineGetter(navigator, 'vendorSub', () => '');
    defineGetter(navigator, 'productSub', () => '20030107');
    defineGetter(navigator, 'product', () => 'Gecko');
    defineGetter(navigator, 'appName', () => 'Netscape');
    defineGetter(navigator, 'appCodeName', () => 'Mozilla');
    defineGetter(navigator, 'appVersion', () => navigator.userAgent.replace('Mozilla/', ''));
    defineGetter(navigator, 'doNotTrack', () => null);
    defineGetter(navigator, 'cookieEnabled', () => true);
    defineGetter(navigator, 'onLine', () => true);
    defineGetter(navigator, 'pdfViewerEnabled', () => true);
    // navigator.platform 必须与 UA 平台一致（Windows UA → Win32）
    // 2026-08-01 新增：Linux 容器 navigator.platform 默认是 'Linux x86_64'，
    //            与 Windows UA 矛盾，Baxia 检测到不一致直接判定机器人
    defineGetter(navigator, 'platform', () => 'Win32');

    // ===== 5. navigator.userAgentData (Client Hints) — Chrome 131+ 必有 =====
    // 2026-08-01 重大修复：无条件覆盖（不判断 if (!navigator.userAgentData)）
    // 原因：patchright 在 Linux 容器中可能自动设置 userAgentData.platform='Linux'，
    //       导致 UA（Windows）与 Client Hints（Linux）矛盾，Baxia 直接判定机器人。
    //       必须强制覆盖为 Windows，确保 UA、Client Hints、navigator.platform 三者一致。
    {
      const brands = [
        { brand: 'Google Chrome', version: '131' },
        { brand: 'Chromium', version: '131' },
        { brand: 'Not_A Brand', version: '24' },
      ];
      try {
        Object.defineProperty(navigator, 'userAgentData', {
          get: () => ({
            brands,
            mobile: false,
            platform: 'Windows',
            getHighEntropyValues: (hints) => Promise.resolve({
              architecture: 'x86',
              bitness: '64',
              brands,
              fullVersionList: brands,
              mobile: false,
              model: '',
              platform: 'Windows',
              platformVersion: '15.0.0',
              uaFullVersion: '131.0.6778.86',
              ...(hints.includes('wow64') ? { wow64: false } : {}),
            }),
            toJSON: () => ({ brands, mobile: false, platform: 'Windows' }),
          }),
          configurable: true,
        });
      } catch (e) {}
    }

    // ===== 6. navigator.connection (Network Information API) =====
    if (!navigator.connection) {
      try {
        Object.defineProperty(navigator, 'connection', {
          get: () => ({
            effectiveType: '4g',
            rtt: 50,
            downlink: 10,
            saveData: false,
            type: 'wifi',
            addEventListener: () => {},
            removeEventListener: () => {},
            dispatchEvent: () => false,
            onchange: null,
          }),
          configurable: true,
        });
      } catch (e) {}
    }

    // ===== 7. navigator.getBattery() — 真人浏览器必有 =====
    if (!navigator.getBattery) {
      try {
        navigator.getBattery = () => Promise.resolve({
          charging: true,
          chargingTime: 0,
          dischargingTime: Infinity,
          level: 0.99,
          addEventListener: () => {},
          removeEventListener: () => {},
          dispatchEvent: () => false,
          onchargingchange: null,
          onchargingtimechange: null,
          ondischargingtimechange: null,
          onlevelchange: null,
        });
      } catch (e) {}
    }

    // ===== 8. MediaDevices.enumerateDevices — 真人有音视频设备 =====
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
      const origEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
      navigator.mediaDevices.enumerateDevices = () => origEnumerate().then((devices) => {
        if (devices && devices.length > 0) return devices;
        // 空设备列表是 headless 信号，返回模拟设备
        return [
          { kind: 'audioinput', deviceId: 'default', groupId: 'default', label: '' },
          { kind: 'audiooutput', deviceId: 'default', groupId: 'default', label: '' },
          { kind: 'videoinput', deviceId: 'default', groupId: 'default', label: '' },
        ];
      });
    }

    // ===== 9. WebGL vendor/renderer（避免 SwiftShader） =====
    const patchWebGL = (proto) => {
      if (!proto || !proto.getParameter) return;
      const orig = proto.getParameter;
      proto.getParameter = function(param) {
        // UNMASKED_VENDOR_WEBGL = 0x9245, UNMASKED_RENDERER_WEBGL = 0x9246
        if (param === 37445) return 'Google Inc. (NVIDIA)';
        if (param === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)';
        // VENDOR = 0x1F00, RENDERER = 0x1F01
        if (param === 7936) return 'WebKit';
        if (param === 7937) return 'WebKit WebGL';
        return orig.call(this, param);
      };
    };
    try { patchWebGL(WebGLRenderingContext && WebGLRenderingContext.prototype); } catch (e) {}
    if (typeof WebGL2RenderingContext !== 'undefined') {
      try { patchWebGL(WebGL2RenderingContext.prototype); } catch (e) {}
    }

    // ===== 10. Canvas 指纹微扰动 =====
    // headless Canvas 指纹固定，注入微小噪声改变哈希
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
      try {
        const ctx = this.getContext('2d');
        if (ctx) {
          const w = this.width, h = this.height;
          if (w > 0 && h > 0 && w < 4096 && h < 4096) {
            const img = ctx.getImageData(0, 0, w, h);
            // 3% 像素 R 通道 ±1 噪声（视觉不可见，改变指纹哈希）
            for (let i = 0; i < img.data.length; i += 4) {
              if (Math.random() < 0.03) {
                img.data[i] = (img.data[i] + (Math.random() < 0.5 ? -1 : 1)) & 0xff;
              }
            }
            ctx.putImageData(img, 0, 0);
          }
        }
      } catch (e) {}
      return origToDataURL.apply(this, args);
    };

    // ===== 11. AudioContext 指纹扰动 =====
    // headless AudioContext 返回固定值，Baxia 可据此识别
    const origCreateAnalyser = (window.AudioContext || window.webkitAudioContext);
    if (origCreateAnalyser && origCreateAnalyser.prototype) {
      const origGetFloatFrequencyData = origCreateAnalyser.prototype.__lookupGetter__('getFloatFrequencyData');
      // 检测 createAnalyser 后的 frequencyBinCount 是否为固定值
      try {
        const origCreate = origCreateAnalyser.prototype.createAnalyser;
        origCreateAnalyser.prototype.createAnalyser = function() {
          const analyser = origCreate.call(this);
          const origGetFloat = analyser.getFloatFrequencyData.bind(analyser);
          analyser.getFloatFrequencyData = function(array) {
            origGetFloat(array);
            // 注入 ±0.0001 微噪声（不影响音频分析，但改变指纹）
            for (let i = 0; i < array.length; i++) {
              array[i] += (Math.random() - 0.5) * 0.0001;
            }
          };
          return analyser;
        };
      } catch (e) {}
    }

    // ===== 12. WebRTC IP 泄漏防护 =====
    // headless WebRTC 会暴露内网 IP，与公网 IP 不一致即被识别
    try {
      const origRTC = window.RTCPeerConnection;
      if (origRTC) {
        window.RTCPeerConnection = function(...args) {
          const pc = new origRTC(...args);
          const origCreateDataChannel = pc.createDataChannel.bind(pc);
          pc.createDataChannel = function(...dcArgs) {
            return origCreateDataChannel(...dcArgs);
          };
          return pc;
        };
        window.RTCPeerConnection.prototype = origRTC.prototype;
        if (window.webkitRTCPeerConnection) {
          window.webkitRTCPeerConnection = window.RTCPeerConnection;
        }
      }
    } catch (e) {}

    // ===== 13. window.outerWidth/outerHeight =====
    // headless 下 outerWidth==innerWidth，真人浏览器 outerWidth > innerWidth（有窗口边框）
    try {
      Object.defineProperty(window, 'outerWidth', {
        get: () => window.innerWidth + 16,
        configurable: true,
      });
      Object.defineProperty(window, 'outerHeight', {
        get: () => window.innerHeight + 88,
        configurable: true,
      });
    } catch (e) {}

    // ===== 14. permissions 与 Notification 一致性 =====
    if (navigator.permissions && navigator.permissions.query) {
      const orig = navigator.permissions.query.bind(navigator.permissions);
      navigator.permissions.query = (params) => {
        if (params && params.name === 'notifications') {
          const state = (typeof Notification !== 'undefined' && Notification.permission) || 'default';
          return Promise.resolve({ state, onchange: null, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false });
        }
        if (params && params.name === 'geolocation') {
          return Promise.resolve({ state: 'prompt', onchange: null, addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false });
        }
        return orig(params);
      };
    }

    // ===== 15. speechSynthesis.getVoices — headless 返回空数组 =====
    if (window.speechSynthesis) {
      const origGetVoices = window.speechSynthesis.getVoices.bind(window.speechSynthesis);
      window.speechSynthesis.getVoices = () => {
        const voices = origGetVoices();
        if (voices && voices.length > 0) return voices;
        // 返回中文和英文语音
        return [
          { voiceURI: 'Microsoft Huihui - Chinese (Simplified, China)', name: 'Microsoft Huihui - Chinese (Simplified, China)', lang: 'zh-CN', localService: true, default: true },
          { voiceURI: 'Microsoft Kangkang - Chinese (Simplified, China)', name: 'Microsoft Kangkang - Chinese (Simplified, China)', lang: 'zh-CN', localService: true, default: false },
          { voiceURI: 'Microsoft Zira - English (United States)', name: 'Microsoft Zira - English (United States)', lang: 'en-US', localService: true, default: false },
        ];
      };
    }

    // ===== 16. 隐藏 CDP / Playwright 注入痕迹 =====
    const kill = (obj) => {
      try {
        Object.keys(obj).forEach((k) => {
          if (/^cdc_|\$cdc_|__playwright|__pw_|__puppeteer/.test(k)) {
            try { delete obj[k]; } catch (e) {}
          }
        });
      } catch (e) {}
    };
    kill(window);
    kill(document);

    // ===== 17. 修复 iframe 的 navigator.webdriver（同源 iframe） =====
    try {
      const desc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
      if (desc) {
        Object.defineProperty(Navigator.prototype, 'webdriver', {
          get: () => undefined,
          configurable: true,
        });
      }
    } catch (e) {}

    // ===== 18. 修复 Function.prototype.toString 检测 =====
    // 部分检测脚本通过 toString 检查函数是否被重写（native code vs 自定义）
    // 让重写的函数 toString 仍返回 [native code]
    const nativeToStringFn = Function.prototype.toString;
    const fns = new WeakMap();
    const fakeNative = (fn, original) => {
      fns.set(fn, original || fn);
      return fn;
    };
    Function.prototype.toString = function() {
      if (fns.has(this)) {
        return nativeToStringFn.call(fns.get(this));
      }
      return nativeToStringFn.call(this);
    };
    fakeNative(Function.prototype.toString, nativeToStringFn);

    // ===== 19. navigator.webdriver 的 toString 检测 =====
    // 某些检测用 Object.getOwnPropertyDescriptor(navigator, 'webdriver').get.toString()
    // 确保返回 native code
    try {
      const wdDesc = Object.getOwnPropertyDescriptor(navigator, 'webdriver');
      if (wdDesc && wdDesc.get) {
        fakeNative(wdDesc.get, () => undefined);
      }
    } catch (e) {}

    // ===== 20. window.screen 属性一致性 =====
    try {
      Object.defineProperty(screen, 'colorDepth', { get: () => 24, configurable: true });
      Object.defineProperty(screen, 'pixelDepth', { get: () => 24, configurable: true });
      // availTop/availLeft 通常为 0（非多屏）
      Object.defineProperty(screen, 'availTop', { get: () => 0, configurable: true });
      Object.defineProperty(screen, 'availLeft', { get: () => 0, configurable: true });
    } catch (e) {}

    // ===== 21. 修复 Notification.permission =====
    if (window.Notification) {
      try {
        Object.defineProperty(Notification, 'permission', { get: () => 'default', configurable: true });
      } catch (e) {}
    }

    // ===== 22. 隐藏自动化相关的 console.debug 特征 =====
    // 某些检测用 console.debug.bind(console) 检查是否被 hook
    try {
      const origDebug = console.debug;
      Object.defineProperty(console, 'debug', {
        get: () => origDebug,
        configurable: true,
      });
    } catch (e) {}

  } catch (e) {}
})();
"""


# patchright 模式专用：只包含 patchright 不处理的高级指纹规避。
# patchright 自动处理 navigator.webdriver / userAgentData / CDP 痕迹，
# 但不处理 window.chrome / WebGL/Canvas/Audio/WebRTC/connection/getBattery/MediaDevices/speechSynthesis 等指纹维度。
# 注入这个脚本补充高级指纹规避，避免与 patchright 冲突。
_ADVANCED_FINGERPRINT_SCRIPT = r"""
(() => {
  const defineGetter = (obj, prop, getter) => {
    try {
      Object.defineProperty(obj, prop, { get: getter, configurable: true });
    } catch (e) {}
  };

  try {
    // ===== 1. window.chrome 完整对象（patchright 不补全 chrome.runtime，Baxia 检测 chrome.runtime） =====
    // 用 Object.defineProperty 强制定义，避免 patchright 用 writable:false 导致赋值静默失败
    if (!window.chrome) {
      try { Object.defineProperty(window, 'chrome', { value: {}, writable: true, configurable: true }); } catch (e) { window.chrome = {}; }
    }
    // 强制设置 runtime（即使 chrome 对象是只读的）
    const runtimeObj = {
      OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
      OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' },
      PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
      PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
      id: undefined,
      connect: () => {},
      sendMessage: () => {},
    };
    try {
      Object.defineProperty(window.chrome, 'runtime', { value: runtimeObj, writable: true, configurable: true, enumerable: true });
    } catch (e) {
      try { window.chrome.runtime = runtimeObj; } catch (e2) {}
    }
    if (!window.chrome.csi) {
      try { Object.defineProperty(window.chrome, 'csi', { value: () => ({ startE: Date.now() - Math.floor(Math.random() * 3000 + 2000), onloadT: Date.now(), pageT: Math.random() * 2000 + 500, tran: 15 }), writable: true, configurable: true }); } catch (e) { window.chrome.csi = () => ({ startE: Date.now() - 2000, onloadT: Date.now(), pageT: 500, tran: 15 }); }
    }
    if (!window.chrome.loadTimes) {
      const t = Date.now() / 1000;
      const ltFn = () => ({
        commitLoadTime: t - 4, connectionInfo: 'h2', finishDocumentLoadTime: t - 2,
        finishLoadTime: t - 1.5, firstPaintAfterLoadTime: t - 1.8, firstPaintTime: t - 3,
        navigationType: 'Other', npnNegotiatedProtocol: 'h2', requestTime: t - 5,
        startLoadTime: t - 5, wasAlternateProtocolAvailable: false,
        wasFetchedViaSpdy: true, wasNpnNegotiated: true,
      });
      try { Object.defineProperty(window.chrome, 'loadTimes', { value: ltFn, writable: true, configurable: true }); } catch (e) { window.chrome.loadTimes = ltFn; }
    }
    if (!window.chrome.app) {
      const appObj = { isInstalled: false, InstallState: { DISABLED: 'disabled', INSTALLED: 'installed', NOT_INSTALLED: 'not_installed' }, RunningState: { CANNOT_RUN: 'cannot_run', READY_TO_RUN: 'ready_to_run', RUNNING: 'running' } };
      try { Object.defineProperty(window.chrome, 'app', { value: appObj, writable: true, configurable: true }); } catch (e) { window.chrome.app = appObj; }
    }

    // ===== 2. navigator.languages（patchright 只设 zh-CN，真人有多个语言） =====
    defineGetter(navigator, 'languages', () => ['zh-CN', 'zh', 'en-US', 'en']);

    // ===== 3. speechSynthesis.getVoices（headless 返回空，真人有 voices） =====
    try {
      if (window.speechSynthesis) {
        const origGetVoices = window.speechSynthesis.getVoices.bind(window.speechSynthesis);
        const fakeVoices = [
          { default: true, lang: 'zh-CN', localService: true, name: 'Microsoft Huihui - Chinese (Simplified, China)', voiceURI: 'Microsoft Huihui - Chinese (Simplified, China)' },
          { default: false, lang: 'zh-CN', localService: true, name: 'Microsoft Kangkang - Chinese (Simplified, China)', voiceURI: 'Microsoft Kangkang - Chinese (Simplified, China)' },
          { default: false, lang: 'zh-TW', localService: true, name: 'Microsoft Hanhan - Chinese (Traditional, Taiwan)', voiceURI: 'Microsoft Hanhan - Chinese (Traditional, Taiwan)' },
          { default: false, lang: 'en-US', localService: true, name: 'Microsoft Zira - English (United States)', voiceURI: 'Microsoft Zira - English (United States)' },
          { default: false, lang: 'en-US', localService: true, name: 'Microsoft David - English (United States)', voiceURI: 'Microsoft David - English (United States)' },
        ];
        window.speechSynthesis.getVoices = () => {
          const real = origGetVoices();
          return (real && real.length > 0) ? real : fakeVoices;
        };
      }
    } catch (e) {}

    // ===== 4. navigator.connection (Network Information API) =====
    if (!navigator.connection) {
      try {
        Object.defineProperty(navigator, 'connection', {
          get: () => ({
            effectiveType: '4g', rtt: 50, downlink: 10, saveData: false, type: 'wifi',
            addEventListener: () => {}, removeEventListener: () => {},
            dispatchEvent: () => false, onchange: null,
          }),
          configurable: true,
        });
      } catch (e) {}
    }

    // ===== 5. navigator.getBattery() =====
    if (!navigator.getBattery) {
      try {
        navigator.getBattery = () => Promise.resolve({
          charging: true, chargingTime: 0, dischargingTime: Infinity, level: 0.99,
          addEventListener: () => {}, removeEventListener: () => {},
          dispatchEvent: () => false,
          onchargingchange: null, onchargingtimechange: null,
          ondischargingtimechange: null, onlevelchange: null,
        });
      } catch (e) {}
    }

    // ===== 6. MediaDevices.enumerateDevices =====
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
      const origEnumerate = navigator.mediaDevices.enumerateDevices.bind(navigator.mediaDevices);
      navigator.mediaDevices.enumerateDevices = () => origEnumerate().then((devices) => {
        if (devices && devices.length > 0) return devices;
        return [
          { kind: 'audioinput', deviceId: 'default', groupId: 'default', label: '' },
          { kind: 'audiooutput', deviceId: 'default', groupId: 'default', label: '' },
          { kind: 'videoinput', deviceId: 'default', groupId: 'default', label: '' },
        ];
      });
    }

    // ===== 7. WebGL vendor/renderer（Docker 容器无 GPU 必须伪造） =====
    // 2026-08-01 修复：容器内 Chrome getContext('webgl') 返回 null（无 GPU），
    // Baxia 检测到 no-webgl 直接识别为机器人。
    // 方案：patch HTMLCanvasElement.prototype.getContext，当 webgl 返回 null 时
    // 返回一个假 WebGL 上下文，getParameter 返回 NVIDIA GTX 1660 SUPER。
    // 注意：不用 swiftshader（软件渲染导致 page.mouse 卡住）。
    const FAKE_VENDOR = 'Google Inc. (NVIDIA)';
    const FAKE_RENDERER = 'ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 SUPER Direct3D11 vs_5_0 ps_5_0)';
    const origGetContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) {
      const ctx = origGetContext.call(this, type, ...args);
      // 只在请求 webgl/webgl2 且返回 null 时返回假上下文
      if (!ctx && (type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2')) {
        // 返回一个假 WebGL 上下文对象
        const fakeCtx = {
          getParameter: (p) => {
            // UNMASKED_VENDOR_WEBGL = 0x9245
            if (p === 37445) return FAKE_VENDOR;
            // UNMASKED_RENDERER_WEBGL = 0x9246
            if (p === 37446) return FAKE_RENDERER;
            // VENDOR = 0x1F00
            if (p === 7936) return 'WebKit';
            // RENDERER = 0x1F01
            if (p === 7937) return 'WebKit WebGL';
            // VERSION = 0x1F02
            if (p === 7938) return 'WebGL 1.0 (OpenGL ES 2.0 Chromium)';
            // SHADING_LANGUAGE_VERSION = 0x8B8C
            if (p === 35724) return 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)';
            // MAX_VERTEX_ATTRIBS = 0x8869
            if (p === 34921) return 16;
            // MAX_TEXTURE_SIZE = 0x0D33
            if (p === 3379) return 16384;
            // MAX_RENDERBUFFER_SIZE = 0x84E8
            if (p === 34024) return 16384;
            return null;
          },
          getExtension: (name) => {
            if (name === 'WEBGL_debug_renderer_info') {
              return { UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 };
            }
            return null;
          },
          getSupportedExtensions: () => [
            'ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float',
            'EXT_disjoint_timer_query', 'EXT_float_blend', 'EXT_frag_depth',
            'EXT_shader_texture_lod', 'EXT_texture_compression_bptc', 'EXT_texture_compression_rgtc',
            'EXT_texture_filter_anisotropic', 'EXT_sRGB', 'OES_element_index_uint',
            'OES_fbo_render_mipmap', 'OES_standard_derivatives', 'OES_texture_float',
            'OES_texture_float_linear', 'OES_texture_half_float', 'OES_texture_half_float_linear',
            'OES_vertex_array_object', 'WEBGL_color_buffer_float', 'WEBGL_compressed_texture_s3tc',
            'WEBGL_compressed_texture_s3tc_srgb', 'WEBGL_debug_renderer_info',
            'WEBGL_debug_shaders', 'WEBGL_depth_texture', 'WEBGL_draw_buffers',
            'WEBGL_lose_context', 'WEBGL_multi_draw',
          ],
          canvas: this,
          drawingBufferWidth: this.width || 300,
          drawingBufferHeight: this.height || 150,
          // 常用方法 stub
          activeTexture: () => {}, bindBuffer: () => {}, bindFramebuffer: () => {},
          bindRenderbuffer: () => {}, bindTexture: () => {}, blendFunc: () => {},
          bufferData: () => {}, checkFramebufferStatus: () => 36053, clear: () => {},
          clearColor: () => {}, clearDepth: () => {}, compileShader: () => {},
          createBuffer: () => ({}), createFramebuffer: () => ({}), createProgram: () => ({}),
          createRenderbuffer: () => ({}), createShader: () => ({}), createTexture: () => ({}),
          deleteBuffer: () => {}, deleteFramebuffer: () => {}, deleteProgram: () => {},
          deleteRenderbuffer: () => {}, deleteShader: () => {}, deleteTexture: () => {},
          depthFunc: () => {}, disable: () => {}, disableVertexAttribArray: () => {},
          drawArrays: () => {}, drawElements: () => {}, enable: () => {},
          enableVertexAttribArray: () => {}, finish: () => {}, flush: () => {},
          framebufferRenderbuffer: () => {}, framebufferTexture2D: () => {},
          generateMipmap: () => {}, getAttribLocation: () => 0, getProgramParameter: () => 35714,
          getProgramInfoLog: () => '', getShaderParameter: () => 35714, getShaderInfoLog: () => '',
          getUniformLocation: () => ({}), linkProgram: () => {}, pixelStorei: () => {},
          shaderSource: () => {}, texImage2D: () => {}, texParameteri: () => {},
          uniform1f: () => {}, uniform1i: () => {}, uniform2f: () => {}, uniform3f: () => {},
          uniform4f: () => {}, uniformMatrix4fv: () => {}, useProgram: () => {},
          vertexAttribPointer: () => {}, viewport: () => {},
          isContextLost: () => false, getContextAttributes: () => ({
            alpha: true, antialias: true, depth: true, failIfMajorPerformanceCaveat: false,
            premultipliedAlpha: true, preserveDrawingBuffer: false, stencil: false,
            desynchronized: false, powerPreference: 'default',
          }),
        };
        return fakeCtx;
      }
      return ctx;
    };

    // ===== 8. Canvas 指纹微扰动 =====
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(...args) {
      try {
        const ctx = this.getContext('2d');
        if (ctx) {
          const w = this.width, h = this.height;
          if (w > 0 && h > 0 && w < 4096 && h < 4096) {
            const img = ctx.getImageData(0, 0, w, h);
            for (let i = 0; i < img.data.length; i += 4) {
              if (Math.random() < 0.03) {
                img.data[i] = (img.data[i] + (Math.random() < 0.5 ? -1 : 1)) & 0xff;
              }
            }
            ctx.putImageData(img, 0, 0);
          }
        }
      } catch (e) {}
      return origToDataURL.apply(this, args);
    };

    // ===== 9. AudioContext 指纹扰动 =====
    const origCreateAnalyser = (window.AudioContext || window.webkitAudioContext);
    if (origCreateAnalyser && origCreateAnalyser.prototype) {
      try {
        const origCreate = origCreateAnalyser.prototype.createAnalyser;
        origCreateAnalyser.prototype.createAnalyser = function() {
          const analyser = origCreate.call(this);
          const origGetFloat = analyser.getFloatFrequencyData.bind(analyser);
          analyser.getFloatFrequencyData = function(array) {
            origGetFloat(array);
            for (let i = 0; i < array.length; i++) {
              array[i] += (Math.random() - 0.5) * 0.0001;
            }
          };
          return analyser;
        };
      } catch (e) {}
    }

    // ===== 10. WebRTC IP 泄漏防护 =====
    try {
      const origRTC = window.RTCPeerConnection;
      if (origRTC) {
        window.RTCPeerConnection = function(...args) {
          const pc = new origRTC(...args);
          const origCreateDataChannel = pc.createDataChannel.bind(pc);
          pc.createDataChannel = function(...dcArgs) {
            return origCreateDataChannel(...dcArgs);
          };
          return pc;
        };
        window.RTCPeerConnection.prototype = origRTC.prototype;
        if (window.webkitRTCPeerConnection) {
          window.webkitRTCPeerConnection = window.RTCPeerConnection;
        }
      }
    } catch (e) {}

    // ===== 11. isTrusted 补丁（2026-08-01 新增，针对 Baxia FireyeJS 事件检测） =====
    // 原理：Baxia FireyeJS 在事件监听器中读取 event.isTrusted 检测机器人
    // - 原生浏览器：CDP 事件 isTrusted=true，JS dispatch 事件 isTrusted=false
    // - 补丁后：JS dispatch 事件 isTrusted=true（通过 prototype getter）
    // 关键：在页面加载前（add_init_script）补丁，确保 Baxia 加载时补丁已生效
    // 隐蔽性：用 native toString 伪装，防止 toString 检测
    try {
      const origDefineProperty = Object.defineProperty;
      const fakeIsTrustedGetter = function() { return true; };
      // 伪装 toString（防止 Function.prototype.toString 检测）
      try {
        fakeIsTrustedGetter.toString = Object.getOwnPropertyDescriptor(
          Function.prototype, 'toString'
        ).value.bind(function toString() { return 'function isTrusted() { [native code] }'; });
      } catch(e) {}
      origDefineProperty(Event.prototype, 'isTrusted', {
        get: fakeIsTrustedGetter,
        configurable: true,
      });
    } catch (e) {}

    // ===== 12. sourceCapabilities 补丁（2026-08-01 新增） =====
    // 原理：原生鼠标事件有 sourceCapabilities 属性，JS dispatch 事件没有
    // - Baxia 可能检测 sourceCapabilities 是否存在
    // - 补丁后：所有事件都有 sourceCapabilities
    try {
      const fakeSourceCapabilities = { firesTouchEvents: false, pointerMovementScroll: false };
      const origDefineProperty2 = Object.defineProperty;
      origDefineProperty2(MouseEvent.prototype, 'sourceCapabilities', {
        get: function() { return fakeSourceCapabilities; },
        configurable: true,
      });
    } catch (e) {}

  } catch (e) {}
})();
"""


def get_chrome_user_agent(chrome_path: str) -> str:
    """UA 主版本尽量匹配本机 Chrome，避免 Client Hints 与 UA 不一致。"""
    ver = "131.0.0.0"
    try:
        # Windows: 从 chrome.exe 旁 Version 目录推断，或用 --version
        import re as _re
        out = subprocess.run(
            [chrome_path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        m = _re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", (out.stdout or "") + (out.stderr or ""))
        if m:
            ver = m.group(0)
        else:
            # File version style 146.0.7680.76
            parent = os.path.dirname(chrome_path)
            for name in os.listdir(parent):
                if _re.match(r"^\d+\.\d+\.\d+\.\d+$", name):
                    ver = name
                    break
    except Exception:
        pass
    # 2026-08-01 重大修复：所有平台统一用 Windows UA
    # 原因：闲鱼 PC 端正常用户几乎都是 Windows/Mac，Linux UA（X11; Linux x86_64）
    #       极其可疑。Baxia FireyeJS 检测到 Linux UA 会直接判定为机器人，
    #       导致滑块验证 0% 通过率（无论拖动轨迹多像人类）。
    #       配合 userAgentData.platform='Windows' 和 navigator.platform='Win32' 补丁，
    #       确保 UA、Client Hints、navigator.platform 三者一致。
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/{ver} Safari/537.36"
    )

BAXIA_CONTAINER_SELECTORS = [
    "#nc_1",
    ".nc_wrapper",
    "#baxia-dialog",
    'iframe[src*="baxia"]',
    ".J_MIDDLEWARE_FRAME",
    'iframe[id*="baxia"]',
    ".slide-verify",
    "#nc_1_n1z",
    ".btn_slide",
]

SLIDER_BUTTON_SELECTORS = [
    "#nc_1_n1z",
    ".btn_slide",
    ".nc_iconfont",
    ".slide-btn",
    "#nc_1_n1t",
    ".nc-lang-cnt",
    '[data-role="slider"]',
]

SLIDER_TRACK_SELECTORS = [
    ".nc_scale",
    ".scale_text",
    ".slide-track",
    "#nc_1__scale",
    ".nc-lang",
]

SUCCESS_SELECTORS = [
    ".nc_ok",
    ".success",
    "#nc_1_n1z.success",
    ".icon-success",
    # 2026-08-01 新增：Baxia NoCaptcha 滑块通过后的实际 class 名
    # 原因：Baxia 通过后 class 是 "nc-lang-cnt-success"，不匹配 ".success"
    #       导致 check_solved 误判为未通过，即使滑块已通过
    ".nc-lang-cnt-success",
    ".btn_ok",
    "[class*='nc-lang-cnt-success']",
    "[class*='btn_ok']",
]
FAIL_SELECTORS = [
    ".nc_error",
    ".errloading",
    ".fail",
    "#nc_1_refresh1",
    # 2026-08-01 新增：Baxia 失败后的实际 class 名
    ".nc-lang-cnt-error",
    ".nc-lang-cnt-err",
    "[class*='nc-lang-cnt-error']",
]


def log(msg: str) -> None:
    print(f"[sliderSolve] {msg}", flush=True)


def output_result(result: dict) -> None:
    """最后一行 JSON 供 TypeScript 解析。"""
    print(json.dumps(result, ensure_ascii=False), flush=True)


def find_chrome_path() -> Optional[str]:
    local = os.environ.get("LOCALAPPDATA") or ""
    candidates = [
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None


# ---------- 全自动：全局单飞锁（防止多账号同时开浏览器互相踩风控）----------
_SOLVE_LOCK_PATH = os.path.join(os.environ.get("TEMP") or "/tmp", "xya-slider-solve.lock")
_SEED_PROFILE_DIR = os.path.join(os.environ.get("TEMP") or "/tmp", "xya-slider-seed-v2")
# 持久化 profile 目录：累积浏览历史/Cookie/指纹，让浏览器看起来像真人日常使用
# 关键改进：临时空 profile 是机器人强信号，持久化 profile 有真实浏览痕迹可大幅降低风控
_PERSISTENT_PROFILE_DIR = os.path.join(os.environ.get("TEMP") or "/tmp", "xya-slider-persistent-v3")


def _chrome_stealth_args() -> list[str]:
    """Chrome 反自动化检测启动参数。

    全面覆盖 Playwright/CDP 默认注入的自动化信号：
    - --enable-automation: 导航栏显示"Chrome 正在被自动测试软件控制"
    - --disable-blink-features=AutomationControlled: 屏蔽 navigator.webdriver
    - --disable-features=AutomationControlled: 额外屏蔽 Blink 层自动化标记
    - 其余参数移除 headless/测试特征，模拟真人 Chrome 启动
    """
    return [
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
        # 核心反检测：移除自动化标记
        "--disable-blink-features=AutomationControlled",
        "--disable-features=AutomationControlled",
        # 移除 test-type 标记（Playwright 默认会加 --enable-automation --test-type）
        "--disable-extensions-except=",
        # 语言与区域
        "--lang=zh-CN",
        "--accept-lang=zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        # 禁用部分泄漏 headless 的实验功能
        "--disable-dev-shm-usage",
        "--no-sandbox",
        # 禁用 GPU 时不用 SwiftShader（会用真实 GPU，但需保留 GPU 进程）
        "--disable-gpu-sandbox",
        # 禁用 BackgroundMode（headless 不会后台运行）
        "--disable-background-mode",
        # 禁用 component-updates（headless 不需要）
        "--disable-component-update",
        # 禁用 default-apps（避免首次启动安装默认应用）
        "--disable-default-apps",
        # 禁用 translate（避免弹翻译提示）
        "--disable-translate",
        # 禁用 sync（避免登录同步提示）
        "--disable-sync",
        # 禁用 metrics（避免发送遥测数据泄漏特征）
        "--disable-metrics",
        "--disable-metrics-recalc-only",
        # 禁用 media-stream（避免 permissions 异常）
        "--use-fake-ui-for-media-stream",
        # 密码管理器/凭据服务（headless 不需要，且会弹保存提示）
        "--disable-save-password-bubble",
        "--disable-password-manager-reauthentication",
        # 禁用 infobars（"Chrome 正在被自动测试软件控制"信息栏）
        "--disable-infobars",
        "--disable-notifications",
        # 禁用 permissive notifications
        "--disable-features=Notifications",
        # 禁用 background timer throttling（让定时器更自然）
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        # 禁用回退到 software rendering（让 WebGL 使用真实 GPU）
        "--disable-software-rasterizer",
        # 强制使用 ANGLE（真实 Chrome 默认用 ANGLE，而非 SwiftShader）
        "--use-angle=d3d11",
        # 禁用 pinch（触屏手势，桌面 Chrome 无）
        "--disable-pinch",
        # 禁用 hang monitor（headless 不需要）
        "--disable-hang-monitor",
        # 禁用 IPC flood protection（避免 throttling）
        "--disable-ipc-flooding-protection",
        # 禁用 prompt on multiple downloads
        "--disable-multi-display-mode",
        # 禁用-quic（部分场景 QUIC 被风控识别）
        # 保留 quic，不阻断
    ]


def _resolve_profile_dir(strategy: str = "persistent", cookie_str: str = "") -> str:
    """选择浏览器 profile 目录。

    策略：
    - persistent: 使用持久化 profile（累积历史/cookie/指纹），最大程度模拟真人浏览器
      - 同一 cookie 使用同一 profile 目录（按 cookie 哈希区分），避免多账号共用同一 profile 导致冲突
    - seed: 克隆预热 seed profile（fallback）
    - temp: 临时空 profile（最不安全，仅用于对比测试）

    持久化 profile 是成功率提升的关键：真人 Chrome 有数月浏览历史、
    积累的 cookie/localStorage/IndexedDB，Baxia 可通过这些判断浏览器是否"真实使用过"。
    """
    if strategy == "persistent":
        # 按 cookie 哈希区分 profile 目录，避免多账号共用同一 profile
        # 同一账号每次使用相同的 profile，累积浏览历史；不同账号使用不同 profile，避免 cookie 冲突
        if cookie_str:
            import hashlib as _hashlib
            cookie_hash = _hashlib.md5(cookie_str[:200].encode("utf-8")).hexdigest()[:8]
            profile_dir = os.path.join(_PERSISTENT_PROFILE_DIR, f"acct-{cookie_hash}")
        else:
            profile_dir = _PERSISTENT_PROFILE_DIR
        os.makedirs(profile_dir, exist_ok=True)
        return profile_dir
    if strategy == "seed":
        dest = os.path.join(
            os.environ.get("TEMP") or "/tmp",
            f"chrome-slider-seed-{int(time.time())}-{random.randint(1000, 9999)}",
        )
        return dest
    # temp
    return os.path.join(
        os.environ.get("TEMP") or "/tmp",
        f"chrome-slider-temp-{int(time.time())}-{random.randint(1000, 9999)}",
    )


class _FileLock:
    """跨进程文件锁，保证全自动滑块同一时刻只跑 1 个浏览器。"""

    def __init__(self, path: str, timeout: float = 300.0):
        self.path = path
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._fh = open(self.path, "a+b")
        start = time.time()
        if sys.platform == "win32":
            import msvcrt  # Windows 专属
            while True:
                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                    return self
                except OSError:
                    if time.time() - start > self.timeout:
                        raise TimeoutError(f"等待滑块全局锁超时: {self.path}")
                    time.sleep(0.5)
        else:
            # Linux/Mac 使用 fcntl.flock
            import fcntl
            while True:
                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return self
                except OSError:
                    if time.time() - start > self.timeout:
                        raise TimeoutError(f"等待滑块全局锁超时: {self.path}")
                    time.sleep(0.5)

    def __exit__(self, *args):
        try:
            if self._fh:
                if sys.platform == "win32":
                    import msvcrt
                    try:
                        self._fh.seek(0)
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl
                    try:
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                self._fh.close()
        except Exception:
            pass


def _ignore_chrome_lock_files(dirpath: str, names: list[str]) -> list[str]:
    ignore = set()
    for n in names:
        ln = n.lower()
        if ln in {
            "singletonlock",
            "singletoncookie",
            "singletonsocket",
            "lockfile",
            "runningchromeversion",
        } or ln.endswith(".lock"):
            ignore.add(n)
        # 体积大且无助于指纹的缓存可跳过
        if ln in {"cache", "code cache", "gpu cache", "service worker", "shadercache"}:
            ignore.add(n)
    return list(ignore)


def prepare_profile_dir(dest: str) -> str:
    """准备浏览器配置目录：优先克隆预热 seed，避免空 profile 被秒杀。"""
    if os.path.exists(dest):
        shutil.rmtree(dest, ignore_errors=True)
    os.makedirs(dest, exist_ok=True)

    seed = _SEED_PROFILE_DIR
    seed_default = os.path.join(seed, "Default")
    if os.path.isdir(seed_default):
        try:
            shutil.copytree(seed, dest, dirs_exist_ok=True, ignore=_ignore_chrome_lock_files)
            log(f"已克隆预热 profile: {seed} -> {dest}")
            return dest
        except Exception as e:
            log(f"克隆 seed profile 失败，使用空目录: {e}")
            shutil.rmtree(dest, ignore_errors=True)
            os.makedirs(dest, exist_ok=True)
    return dest


# ============================================================
# Chrome 临时目录清理（2026-08-08 修复）
# ------------------------------------------------------------
# 根因：Python 子进程被 server.ts pkill -9 或异常退出时，finally 里的
# shutil.rmtree 不会执行，chrome-slider-temp-* 会在 2GB tmpfs 中累积，
# 最终所有 browserType.launchPersistentContext 因 "No space left on device"
# 失败（线上 08-07 全部滑块求解失败、20:41 后无新记录）。
# 这里在每次启动浏览器前清扫历史遗留的临时 profile 与 Chrome 单例锁文件，
# 并保证 /tmp 有足够余量；xya-slider-seed-v2 / xya-slider-persistent-v3
# 等预热/持久化 profile 和全局锁文件不在清理范围内。
# ============================================================
_TEMP_SWEEP_PATTERNS = (
    "chrome-slider-temp-",
    "chrome-slider-seed-",
    "chrome-slider-warm-",
    "playwright-slider-",
)
_TEMP_SWEEP_MAX_AGE_SEC = 1800  # 常规清扫：超过 30 分钟
_TEMP_EMERGENCY_MAX_AGE_SEC = 300  # 空间不足时：超过 5 分钟（避免误删并发会话）
_TEMP_MIN_FREE_MB = 512  # Chrome 启动前至少保留 512MB


def _sweep_temp_entries(max_age_sec: float) -> int:
    """删除超过 max_age_sec 的 Chrome 临时 profile / 单例锁文件。"""
    root = os.environ.get("TEMP") or "/tmp"
    removed = 0
    now = time.time()
    try:
        with os.scandir(root) as it:
            for entry in it:
                name = entry.name
                lower = name.lower()
                try:
                    is_dir = entry.is_dir()
                except OSError:
                    continue
                is_temp_dir = is_dir and any(
                    name.startswith(pattern) for pattern in _TEMP_SWEEP_PATTERNS
                )
                is_chrome_singleton = lower.startswith(".com.google.chrome.") or lower.startswith(
                    "com.google.chrome."
                )
                if not (is_temp_dir or is_chrome_singleton):
                    continue
                try:
                    age = now - entry.stat().st_mtime
                except OSError:
                    continue
                if age < max_age_sec:
                    continue
                try:
                    if is_dir:
                        shutil.rmtree(entry.path, ignore_errors=True)
                    else:
                        os.unlink(entry.path)
                    removed += 1
                except OSError:
                    pass
    except OSError:
        pass
    return removed


def ensure_temp_space(
    min_free_mb: int = _TEMP_MIN_FREE_MB,
    sweep_max_age_sec: int = _TEMP_SWEEP_MAX_AGE_SEC,
) -> None:
    """Chrome 启动前清理历史遗留临时文件，确保 /tmp 有足够空间。"""
    root = os.environ.get("TEMP") or "/tmp"
    try:
        free_mb = shutil.disk_usage(root).free / (1024 * 1024)
    except OSError:
        return
    if free_mb < min_free_mb:
        removed = _sweep_temp_entries(_TEMP_EMERGENCY_MAX_AGE_SEC)
        log(
            f"/tmp 空间不足（free={free_mb:.0f}MB < {min_free_mb}MB），"
            f"已紧急清理 {removed} 个近期临时项"
        )
    else:
        removed = _sweep_temp_entries(sweep_max_age_sec)
        if removed:
            log(
                f"已清理 {removed} 个超过 {sweep_max_age_sec}s 的 "
                "Chrome 临时文件/目录"
            )
    try:
        free_mb = shutil.disk_usage(root).free / (1024 * 1024)
    except OSError:
        return
    if free_mb < min_free_mb:
        log(f"/tmp 空间仍不足（free={free_mb:.0f}MB < {min_free_mb}MB）")


async def ensure_seed_profile(playwright, chrome_path: str, ua: str) -> None:
    """首次全自动运行时预热 seed：访问闲鱼首页生成真实 LocalStorage/站点数据。"""
    seed = _SEED_PROFILE_DIR
    marker = os.path.join(seed, ".xya_seed_ready")
    if os.path.isfile(marker):
        return
    log(f"=== 预热 seed Chrome 配置（全自动，仅首次）: {seed} ===")
    if os.path.exists(seed):
        shutil.rmtree(seed, ignore_errors=True)
    os.makedirs(seed, exist_ok=True)
    ctx = None
    try:
        ctx = await playwright.chromium.launch_persistent_context(
            seed,
            headless=False,
            executable_path=chrome_path,
            viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=ua,
            ignore_default_args=["--enable-automation"],
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                "--lang=zh-CN",
            ],
        )
        await ctx.add_init_script(STEALTH_INIT_SCRIPT)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2.5 + random.random() * 2)
        try:
            await page.mouse.wheel(0, 400)
        except Exception:
            pass
        await asyncio.sleep(1.5)
        await page.goto("https://www.goofish.com/im", wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(2.0)
        await ctx.close()
        ctx = None
        with open(marker, "w", encoding="utf-8") as f:
            f.write(str(int(time.time())))
        log("seed profile 预热完成")
    except Exception as e:
        log(f"seed profile 预热失败（可继续）: {e}")
        try:
            if ctx:
                await ctx.close()
        except Exception:
            pass
        # 2026-08-01 修复：预热失败时也创建 marker，避免每次求解都浪费时间重试预热
        # 原因：预热失败（如 X server 问题）不会自愈，反复重试只会浪费 10-20 秒
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write(str(int(time.time())))
            log("预热失败但已创建 marker，后续将跳过预热（使用空 profile）")
        except Exception:
            pass


# Baxia/淘宝风控相关 cookie 字段。
# 这些字段标记了会话的风控状态（punish/封禁），带着它们访问会被服务器持续判定为高风险。
# 清除后让服务器重新评估会话，有助于脱离 punish 状态。
# 保留登录态字段：cookie2/_m_h5_tk/unb/t/_tb_token_/sgcookie/tracknick/csg/havana_lgc2_*/XSRF-TOKEN 等。
_RISK_COOKIE_NAMES = {
    "x5sectag",        # Baxia 风控标签（账号 1/2 都有）
    "x5sec",           # Baxia session 数据（hex 编码 JSON）
    "x5secdata",       # Baxia punish 数据
    "x5pref",          # Baxia 偏好
    "bx-cookie-test",  # Baxia cookie 测试标记
    "tfstk",           # 淘宝风控 token stack（437-477 字节）
    "cbc",             # 风控相关
    "sca",             # 风控相关
    "isg",             # 阿里 ISG 风控指纹
}


def strip_risk_cookies(cookie_str: str) -> str:
    """从 cookie 字符串中移除风控相关字段，返回清理后的 cookie 字符串。

    保留登录态字段，只清除 Baxia/淘宝风控标记字段。
    这样服务器会重新评估会话，有助于脱离 punish 状态。
    """
    kept: list[str] = []
    removed: list[str] = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part:
            continue
        eq = part.find("=")
        if eq <= 0:
            continue
        name = part[:eq].strip()
        if name in _RISK_COOKIE_NAMES:
            removed.append(name)
        else:
            kept.append(part)
    if removed:
        log(f"已清除风控 cookie 字段: {', '.join(removed)}")
    return "; ".join(kept)


def parse_cookie_string(cookie_str: str, domain: str = ".goofish.com") -> list[dict]:
    """解析 Cookie；设置 30 天过期，便于持久化。"""
    expires_future = int(time.time()) + 30 * 24 * 3600
    cookies: list[dict] = []
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part:
            continue
        eq = part.find("=")
        if eq <= 0:
            continue
        name = part[:eq].strip()
        value = part[eq + 1 :].strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": domain,
                "path": "/",
                "expires": expires_future,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax",
            }
        )
    return cookies


async def element_hover_drag(page, button, distance: float, attempt: int = 1) -> None:
    """基于元素 hover 的 page.mouse 拖动：先悬停按钮再按下，减少“点空”。

    2026-08-01 优化：距离精度 ±1px，Y 抖动 ±1px，释放前停顿 200-400ms，终点微调。
    """
    box = await button.bounding_box()
    if not box:
        raise RuntimeError("button box gone")
    sx = box["x"] + box["width"] / 2
    sy = box["y"] + box["height"] / 2
    # 距离精度：仅 ±1px 噪声（原 attempt 调制会偏大 3-8px）
    dist = distance + random.uniform(-1, 1)

    log(f"  元素悬停拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} attempt={attempt}")
    await button.hover(timeout=3000)
    await asyncio.sleep(0.2 + random.random() * 0.3)
    await page.mouse.move(sx, sy, steps=3)
    await asyncio.sleep(0.1 + random.random() * 0.15)
    await page.mouse.down()
    await asyncio.sleep(0.12 + random.random() * 0.18)

    steps = 40 + random.randint(0, 15)
    for i in range(1, steps + 1):
        p = i / steps
        if p < 0.15:
            eased = 0.08 * (p / 0.15) ** 2
        elif p < 0.8:
            mid = (p - 0.15) / 0.65
            eased = 0.08 + 0.82 * (mid * mid * (3 - 2 * mid))
        else:
            tail = (p - 0.8) / 0.2
            eased = 0.9 + 0.1 * math.sin(tail * math.pi / 2)
        x = sx + dist * eased
        # Y 抖动控制在 ±1px（原 ±3px 过大）
        y = sy + random.uniform(-1, 1)
        await page.mouse.move(x, y, steps=1)
        # 速度曲线：慢-快-慢
        if p < 0.15 or p > 0.8:
            await page.wait_for_timeout(25 + random.random() * 30)
        else:
            await page.wait_for_timeout(12 + random.random() * 20)

    # 终点微调
    for _ in range(2 + random.randint(0, 1)):
        await page.mouse.move(sx + dist + random.uniform(-2, 2), sy + random.uniform(-1, 1), steps=1)
        await page.wait_for_timeout(40 + random.random() * 80)
    # 释放前停顿
    await page.wait_for_timeout(200 + random.random() * 200)
    await page.mouse.up()
    await page.wait_for_timeout(80 + random.random() * 120)


def _bezier_points(p0, p1, p2, p3, n: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


# ===== CDP 直接鼠标事件（解决 page.mouse.move() 不设置 deltaX/deltaY 的问题）=====
# 2026-08-01 关键修复：Playwright 的 page.mouse.move() 调用 Input.dispatchMouseEvent
# 时不会传 deltaX/deltaY 参数，导致 event.movementX/movementY 始终为 0。
# 真实鼠标事件 movementX/movementY 反映鼠标移动增量，Baxia FireyeJS 检测到
# movementX=0 的拖动事件会直接判定为机器人（真实鼠标拖动时 movementX 不可能全为 0）。
# 修复方案：用 CDP 直接发送 Input.dispatchMouseEvent，手动设置 deltaX/deltaY。

async def _cdp_mouse_move(cdp_session, x: float, y: float, prev_x: float, prev_y: float,
                          button: str = 'left', buttons: int = 1) -> None:
    """通过 CDP 发送 mouseMoved 事件，包含正确的 deltaX/deltaY。"""
    dx = round(x - prev_x, 2)
    dy = round(y - prev_y, 2)
    await cdp_session.send('Input.dispatchMouseEvent', {
        'type': 'mouseMoved',
        'x': x,
        'y': y,
        'deltaX': dx,
        'deltaY': dy,
        'button': button,
        'buttons': buttons,
        'modifiers': 0,
        'timestamp': 0,  # 0 = 使用当前时间
    })


async def _cdp_mouse_down(cdp_session, x: float, y: float, prev_x: float, prev_y: float) -> None:
    """通过 CDP 发送 mousePressed 事件。"""
    dx = round(x - prev_x, 2)
    dy = round(y - prev_y, 2)
    await cdp_session.send('Input.dispatchMouseEvent', {
        'type': 'mousePressed',
        'x': x,
        'y': y,
        'deltaX': dx,
        'deltaY': dy,
        'button': 'left',
        'buttons': 1,
        'clickCount': 1,
        'modifiers': 0,
        'timestamp': 0,
    })


async def _cdp_mouse_up(cdp_session, x: float, y: float, prev_x: float, prev_y: float) -> None:
    """通过 CDP 发送 mouseReleased 事件。"""
    dx = round(x - prev_x, 2)
    dy = round(y - prev_y, 2)
    await cdp_session.send('Input.dispatchMouseEvent', {
        'type': 'mouseReleased',
        'x': x,
        'y': y,
        'deltaX': dx,
        'deltaY': dy,
        'button': 'left',
        'buttons': 0,
        'clickCount': 1,
        'modifiers': 0,
        'timestamp': 0,
    })


def _xdotool_available() -> bool:
    """检查 xdotool 是否可用（容器内安装后可用，本地开发机可能没有）。"""
    try:
        r = subprocess.run(['which', 'xdotool'], capture_output=True, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


def _find_chrome_window() -> Optional[int]:
    """找到 Chrome 窗口 ID（用 xdotool search）。

    优先找 Google Chrome 窗口，如果没有就找 Chromium 窗口。
    返回窗口 ID（int），找不到返回 None。
    """
    try:
        # 搜索 Chrome 窗口（class 名包含 chrome）
        r = subprocess.run(
            ['xdotool', 'search', '--onlyvisible', '--class', 'chrome'],
            capture_output=True, timeout=3
        )
        if r.returncode == 0:
            wins = r.stdout.decode().strip().split('\n')
            wins = [int(w) for w in wins if w.strip()]
            if wins:
                # 返回最后一个（最新的窗口，通常是弹出的消息页）
                return wins[-1]
    except Exception:
        pass
    return None


def _get_window_position(win_id: int) -> tuple[int, int]:
    """获取窗口在屏幕上的位置（outer top-left）。"""
    try:
        r = subprocess.run(
            ['xdotool', 'getwindowgeometry', '--shell', str(win_id)],
            capture_output=True, timeout=3
        )
        if r.returncode == 0:
            lines = r.stdout.decode().strip().split('\n')
            x, y = 0, 0
            for line in lines:
                if line.startswith('X='):
                    x = int(line.split('=')[1])
                elif line.startswith('Y='):
                    y = int(line.split('=')[1])
            return x, y
    except Exception:
        pass
    return 0, 0


async def xdotool_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> bool:
    """X11 系统级鼠标拖动（2026-08-01 重大突破，绕过 CDP 检测）。

    核心原理（针对 Baxia FireyeJS 的 CDP 检测）：
    - xdotool 在 X11 层生成真实鼠标事件（MotionNotify/ButtonPress/ButtonRelease）
    - 这些事件来自"系统输入设备"，不经过 Chrome CDP 协议
    - Baxia 的 JS 无法区分 xdotool 事件和真实硬件鼠标事件
    - 事件 isTrusted=true，无 CDP 痕迹，无 movementX=0 问题

    坐标映射（2026-08-01 修复：用 xdotool search 获取真实窗口位置）：
    - bounding_box() 返回视口坐标（相对于 Chrome 视口）
    - xdotool 用 X11 屏幕坐标
    - 屏幕坐标 = 窗口位置 + chrome_bar + 视口坐标
    - 窗口位置通过 xdotool getwindowgeometry 获取（不依赖 window.screenX）

    Returns:
        True 表示 xdotool 拖动已执行，False 表示不可用已回退
    """
    if not _xdotool_available():
        log(f"  物理拖动[xdotool]: xdotool 不可用，回退到 CDP")
        await human_physics_drag(page, start_x, start_y, distance, attempt)
        return False

    # 找到 Chrome 窗口
    win_id = _find_chrome_window()
    if not win_id:
        log(f"  物理拖动[xdotool]: 未找到 Chrome 窗口，回退到 CDP")
        await human_physics_drag(page, start_x, start_y, distance, attempt)
        return False

    # 激活窗口（确保有焦点接收鼠标事件）
    try:
        subprocess.run(['xdotool', 'windowactivate', str(win_id)],
                       timeout=2, capture_output=True)
        await asyncio.sleep(0.1)
    except Exception:
        pass

    # 2026-08-02 重大修复：用 window.screenX/screenY 获取精确窗口位置
    # 原因：xdotool getwindowgeometry 返回 (0,0)，但 window.screenX/screenY 可能不同。
    #       Chrome --window-position=0,0 设置的是窗口外框位置，
    #       但窗口装饰（标题栏、边框）会占用空间，导致客户区不在 (0,0)。
    #       window.screenX/screenY 是浏览器窗口在屏幕上的实际位置，
    #       更准确反映视口在屏幕中的位置。
    # chrome_bar = outerHeight - innerHeight（标签栏+地址栏+书签栏等）
    try:
        offset = await page.evaluate("""() => ({
            screenX: window.screenX,
            screenY: window.screenY,
            outerHeight: window.outerHeight || window.innerHeight,
            innerHeight: window.innerHeight,
            outerWidth: window.outerWidth || window.innerWidth,
            innerWidth: window.innerWidth,
        })""")
        win_x = int(offset.get('screenX', 0))
        win_y = int(offset.get('screenY', 0))
        chrome_bar_h = max(0, int(offset.get('outerHeight', 0)) - int(offset.get('innerHeight', 0)))
        log(f"  [xdotool坐标] window.screenX={win_x} screenY={win_y} "
            f"outerH={offset.get('outerHeight')} innerH={offset.get('innerHeight')} "
            f"chrome_bar={chrome_bar_h}")
    except Exception as e:
        log(f"  [xdotool坐标] page.evaluate 失败: {e}，回退到 xdotool getwindowgeometry")
        win_x, win_y = _get_window_position(win_id)
        chrome_bar_h = 100  # 默认值

    # 视口坐标 → 屏幕坐标
    # screen = window_position + chrome_bar + viewport
    sx = win_x + chrome_bar_h * 0 + start_x + random.uniform(-0.5, 0.5)  # X 不加 chrome_bar
    sy = win_y + chrome_bar_h + start_y + random.uniform(-0.5, 0.5)
    dist = distance + random.uniform(-1, 1)

    # 拖动参数
    total_time_ms = 700 + random.random() * 600  # 0.7-1.3 秒
    steps = 100 + random.randint(0, 40)  # 100-140 步
    avg_delay = total_time_ms / steps

    # Y 轴漂移和抖动
    y_drift_amp = 2.0 + random.random() * 3.0
    y_drift_phase = random.random() * math.pi * 2
    tremor_amp = 0.5 + random.random() * 1.0

    # 过冲
    overshoot_px = random.uniform(2, 6)

    log(f"  物理拖动[xdotool-X11]: viewport=({start_x:.1f},{start_y:.1f}) "
        f"screen=({sx:.1f},{sy:.1f}) dist={dist:.1f} steps={steps} time={total_time_ms:.0f}ms "
        f"win=({win_x},{win_y}) chrome_bar={chrome_bar_h} win_id={win_id} "
        f"tremor={tremor_amp:.1f}px drift={y_drift_amp:.1f}px overshoot={overshoot_px:.1f}px attempt={attempt}")

    try:
        # 移动到起始位置（用 --sync 确保鼠标移动完成）
        subprocess.run(['xdotool', 'mousemove', '--sync', str(int(sx)), str(int(sy))],
                       check=True, timeout=2, capture_output=True)
        await asyncio.sleep(0.15 + random.random() * 0.1)

        # 按下鼠标
        subprocess.run(['xdotool', 'mousedown', '1'],
                       check=True, timeout=2, capture_output=True)
        await asyncio.sleep(0.08 + random.random() * 0.12)

        # Minimum-Jerk 轨迹拖动（x(t) = 10t³ - 15t⁴ + 6t⁵）
        last_x = sx
        for i in range(steps):
            t = (i + 1) / steps
            jerk_pos = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5
            target_x = sx + dist * jerk_pos + random.uniform(-0.2, 0.2)

            # 确保 X 不回退
            if target_x < last_x:
                target_x = last_x + random.uniform(0.1, 0.5)

            # Y 轴漂移 + 抖动
            y_drift = math.sin(t * math.pi + y_drift_phase) * y_drift_amp * 0.3
            y_tremor = random.uniform(-tremor_amp, tremor_amp)
            if t > 0.7:
                y_tremor *= (1.0 - (t - 0.7) / 0.3 * 0.5)
            target_y = sy + y_drift + y_tremor

            subprocess.run(['xdotool', 'mousemove', str(int(target_x)), str(int(target_y))],
                           check=True, timeout=2, capture_output=True)
            last_x = target_x

            delay = avg_delay + random.uniform(-3, 4)
            await asyncio.sleep(max(0.003, delay / 1000))

        # 过冲
        end_x = sx + dist
        overshoot_x = end_x + overshoot_px
        subprocess.run(['xdotool', 'mousemove', str(int(overshoot_x)), str(int(sy + random.uniform(-1, 1)))],
                       check=True, timeout=2, capture_output=True)
        await asyncio.sleep(0.04 + random.random() * 0.06)

        # 修正回终点
        for _ in range(2 + random.randint(0, 1)):
            adjust_x = end_x + random.uniform(-0.8, 0.8)
            adjust_y = sy + random.uniform(-1, 1)
            subprocess.run(['xdotool', 'mousemove', str(int(adjust_x)), str(int(adjust_y))],
                           check=True, timeout=2, capture_output=True)
            await asyncio.sleep(0.04 + random.random() * 0.08)

        # 释放前 Y 轴上移（人类释放时手会自然抬起）
        release_x = end_x + random.uniform(-0.5, 0.5)
        release_y = sy - 2 + random.uniform(-1, 1)
        subprocess.run(['xdotool', 'mousemove', str(int(release_x)), str(int(release_y))],
                       check=True, timeout=2, capture_output=True)
        await asyncio.sleep(0.15 + random.random() * 0.2)

        # 释放
        subprocess.run(['xdotool', 'mouseup', '1'],
                       check=True, timeout=2, capture_output=True)
        await asyncio.sleep(0.05 + random.random() * 0.1)

        # 移开鼠标
        for i in range(3):
            away_x = end_x + 20 + i * 15 + random.uniform(-8, 8)
            away_y = sy + 10 + random.uniform(-15, 15)
            subprocess.run(['xdotool', 'mousemove', str(int(away_x)), str(int(away_y))],
                           check=True, timeout=2, capture_output=True)
            await asyncio.sleep(0.03 + random.random() * 0.04)

        log(f"  物理拖动[xdotool-X11] 完成")
        return True

    except subprocess.CalledProcessError as e:
        log(f"  物理拖动[xdotool-X11] 失败: {e}，回退到 CDP")
        try:
            subprocess.run(['xdotool', 'mouseup', '1'], timeout=1, capture_output=True)
        except Exception:
            pass
        await human_physics_drag(page, start_x, start_y, distance, attempt)
        return False
    except Exception as e:
        log(f"  物理拖动[xdotool-X11] 异常: {type(e).__name__}: {e}，回退到 CDP")
        try:
            subprocess.run(['xdotool', 'mouseup', '1'], timeout=1, capture_output=True)
        except Exception:
            pass
        await human_physics_drag(page, start_x, start_y, distance, attempt)
        return False


async def human_physics_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """基于物理模型的人类拖动模拟（2026-08-01 重大优化，针对 Baxia FireyeJS ML 轨迹检测）。

    核心原理（针对 Baxia FireyeJS 的轨迹 ML 模型优化）：
    1. 非对称加速度曲线：人类加速比减速快（肌肉发力快，收力慢）
       - 加速段（0-30%）：快速加速，用 t² 曲线（起步慢→快速加速）
       - 减速段（30-100%）：缓慢减速，用 1-(1-t)²·⁵ 曲线（慢减速到终点）
       - 之前的 ease-in-out (3t²-2t³) 是对称的，不符合人类运动学
    2. 抖动频率调制：抖动频率随时间变化（不是固定频率）
       - 基频 8-12Hz（医学数据：人类手部生理抖动）
       - 加入 30-50Hz 高频噪声（手指微抖动）
       - 频率随时间随机波动（人类抖动频率不是恒定的）
       - 固定频率会被 ML 频谱分析识别（尖锐峰值）
    3. 抖动幅度调制：抖动幅度在加速段大，减速段小
       - 加速段（0-30%）：幅度 2-3px（肌肉用力，抖动大）
       - 减速段（30-100%）：幅度 1-1.5px（肌肉控制，抖动小）
       - 人类用力时抖动大，控制时抖动小
    4. 过冲回退：人类常会稍微超过终点再回来
       - 先拖到 102-105% 位置
       - 停顿 50-150ms
       - 回退到 100% 位置
       - 这是关键的人类行为特征，机器人的轨迹终点是"死"的
    5. 事件间隔随机性：事件间隔不是固定 8-12ms
       - 加速段：间隔短（5-10ms，快速移动）
       - 减速段：间隔长（10-20ms，慢速移动）
       - 加入随机波动（人类注意力变化）
    6. CDP 事件 isTrusted=true：用 page.mouse（CDP），事件真实
       - patchright 已清理 CDP 痕迹（cdc_, webdriver）
       - CDP 事件 isTrusted=true，无法被检测

    与 JS dispatch 的区别：
    - JS dispatch 的事件 isTrusted=false（补丁无效，Baxia 在页面加载时缓存原始值）
    - CDP 事件 isTrusted=true（真实），是唯一可靠的方案
    """
    # 2026-08-01 重写：最小急动度模型（Minimum-Jerk Profile）
    # 起始位置加入微小噪声（人类无法精准定位到像素级）
    sx = start_x + random.uniform(-0.5, 0.5)
    sy = start_y + random.uniform(-0.5, 0.5)
    # 距离加入 ±1px 噪声（Baxia 精度要求 ±1-2px）
    dist = distance + random.uniform(-1, 1)

    # 总时长 0.7-1.3 秒（人类拖动滑块典型时长）
    total_time_ms = 700 + random.random() * 600
    # 步数 100-140（接近 125Hz 鼠标采样率，256px/120步≈2.1px/步）
    steps = 100 + random.randint(0, 40)
    avg_delay = total_time_ms / steps  # 平均每步延迟

    # Y 轴漂移参数（慢速正弦漂移，模拟手部整体移动趋势）
    y_drift_amp = 2.0 + random.random() * 3.0  # 2-5px 漂移幅度
    y_drift_phase = random.random() * math.pi * 2

    # 抖动参数（随机噪声，非正弦波）
    tremor_amp = 0.5 + random.random() * 1.0  # 0.5-1.5px

    # 随机游走位置噪声参数（累积型，非正弦波）
    noise_accum = 0.0

    # 微停顿：1-2 次随机停顿
    pause_count = random.randint(1, 2)
    pause_positions = sorted(random.sample([0.15, 0.35, 0.55, 0.75], min(pause_count, 4)))
    pause_idx = 0

    # 过冲参数（2-6px 过冲后修正，人类自然行为）
    overshoot_px = random.uniform(2, 6)
    overshoot_pause_ms = 40 + random.random() * 60  # 40-100ms

    log(f"  物理拖动[CDP-minJerk]: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} "
        f"steps={steps} time={total_time_ms:.0f}ms "
        f"tremor={tremor_amp:.1f}px drift={y_drift_amp:.1f}px "
        f"overshoot={overshoot_px:.1f}px attempt={attempt}")

    # ===== 接近阶段：贝塞尔曲线接近滑块（模拟真人瞄准）=====
    approach_start_x = sx - 60 - random.random() * 40
    approach_start_y = sy + 25 + random.uniform(-15, 15)
    ctrl_x = sx - 20 + random.uniform(-10, 10)
    ctrl_y = sy + 15 + random.uniform(-8, 8)
    approach_steps = 12
    for i in range(approach_steps):
        t = (i + 1) / approach_steps
        # 二次贝塞尔曲线
        bx = (1 - t) ** 2 * approach_start_x + 2 * (1 - t) * t * ctrl_x + t * t * sx
        by = (1 - t) ** 2 * approach_start_y + 2 * (1 - t) * t * ctrl_y + t * t * sy
        bx += random.uniform(-0.5, 0.5)
        by += random.uniform(-0.5, 0.5)
        await page.mouse.move(bx, by, steps=1)
        delay = 20 + (1 - t) * 20 + random.uniform(-3, 5)
        await page.wait_for_timeout(max(5, int(delay)))

    # 精准定位到滑块
    await page.wait_for_timeout(100 + random.random() * 150)
    await page.mouse.move(sx + random.uniform(-1, 1), sy + random.uniform(-1, 1), steps=2)
    await page.wait_for_timeout(80 + random.random() * 120)
    await page.mouse.move(sx, sy, steps=1)
    await page.wait_for_timeout(120 + random.random() * 180)

    # ===== mousedown（按下后短暂停顿，准备拖动）=====
    await page.mouse.down()
    await page.wait_for_timeout(80 + random.random() * 120)

    # ===== 拖动主循环：最小急动度轨迹 x(t) = 10t^3 - 15t^4 + 6t^5 =====
    last_x = sx
    for i in range(steps):
        t = (i + 1) / steps  # 归一化时间 0-1

        # 最小急动度位置剖面（Hogan 1984, Flash & Hogan 1985）
        # 产生平滑的钟形速度曲线，是人类 reaching 运动的最优模型
        jerk_pos = 10 * t ** 3 - 15 * t ** 4 + 6 * t ** 5

        # 随机游走位置噪声（累积型，频谱宽带，不被 ML 频谱分析识别）
        noise_accum += random.uniform(-0.12, 0.12)
        noise_accum = max(-1.2, min(1.2, noise_accum))

        target_x = sx + dist * jerk_pos + noise_accum

        # 确保 X 不回退（Baxia 对 X 回退敏感）
        if target_x < last_x:
            target_x = last_x + random.uniform(0.1, 0.5)

        # Y 轴：慢漂移 + 随机抖动
        y_drift = math.sin(t * math.pi + y_drift_phase) * y_drift_amp * 0.3
        y_tremor = random.uniform(-tremor_amp, tremor_amp)
        if t > 0.7:
            # 减速段抖动逐渐减小到 50%
            y_tremor *= (1.0 - (t - 0.7) / 0.3 * 0.5)
        target_y = sy + y_drift + y_tremor

        # X 轴微小噪声（人类手指无法完美直线移动）
        target_x += random.uniform(-0.2, 0.2)

        await page.mouse.move(target_x, target_y, steps=1)

        # 事件间隔：接近 125Hz（6-14ms），加入随机波动
        delay = avg_delay + random.uniform(-3, 4)
        await page.wait_for_timeout(max(3, int(delay)))

        last_x = target_x

        # 微停顿（1-2 次，30-80ms）
        if pause_idx < len(pause_positions) and t >= pause_positions[pause_idx]:
            pause_idx += 1
            pause_ms = 30 + random.random() * 50
            pause_steps = max(1, int(pause_ms / 30))
            for _ in range(pause_steps):
                y_drift_pause = math.sin(t * math.pi + y_drift_phase) * y_drift_amp * 0.3
                await page.mouse.move(
                    last_x + random.uniform(-0.4, 0.4),
                    sy + y_drift_pause + random.uniform(-tremor_amp * 0.6, tremor_amp * 0.6),
                    steps=1
                )
                await page.wait_for_timeout(25 + random.random() * 10)

    # ===== 过冲 + 修正（人类自然行为：先超过 2-6px，再回退）=====
    end_x = sx + dist
    await page.mouse.move(end_x + overshoot_px, sy + random.uniform(-1, 1), steps=1)
    await page.wait_for_timeout(int(overshoot_pause_ms))

    # 修正回终点（2-3 次微调）
    for _ in range(2 + random.randint(0, 1)):
        adjust_x = end_x + random.uniform(-0.8, 0.8)
        adjust_y = sy + random.uniform(-1, 1)
        await page.mouse.move(adjust_x, adjust_y, steps=1)
        await page.wait_for_timeout(40 + random.random() * 80)

    # ===== 释放前：Y 轴微微上移（人类释放时手会自然抬起）=====
    await page.mouse.move(end_x + random.uniform(-0.5, 0.5),
                          sy - 2 + random.uniform(-1, 1), steps=1)
    await page.wait_for_timeout(150 + random.random() * 200)

    # ===== 释放 =====
    await page.mouse.up()
    await page.wait_for_timeout(80 + random.random() * 120)

    # ===== 释放后：鼠标自然移开（模拟人类松手后移开）=====
    for i in range(3):
        away_x = end_x + 20 + i * 15 + random.uniform(-8, 8)
        away_y = sy + 10 + random.uniform(-15, 15)
        await page.mouse.move(away_x, away_y, steps=1)
        await page.wait_for_timeout(30 + random.random() * 40)


async def js_dispatch_drag(page, frame, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """用 JavaScript dispatch 事件模拟拖动（不通过 CDP Input.dispatchMouseEvent）。

    2026-08-01 新增：针对 Baxia FireyeJS 的 CDP 事件检测。

    核心原理：
    - Playwright 的 page.mouse 通过 CDP 的 Input.dispatchMouseEvent 发送鼠标事件
    - Baxia FireyeJS 能检测到 CDP 事件的特征（即使 patchright 清理了 webdriver/cdc_）
    - 本函数在页面内用 JS 创建并 dispatch MouseEvent，绕过 CDP
    - 通过 Object.defineProperty 补丁 Event.prototype.isTrusted，让 isTrusted 返回 true

    风险：
    - isTrusted 补丁可能被 Baxia 检测（通过 Object.getOwnPropertyDescriptor 的 config）
    - 但实测很多反爬系统不检测 isTrusted 的补丁

    优势：
    - 完全绕过 CDP，没有 CDP 事件特征
    - 事件在页面内生成，与真实 DOM 事件一致
    """
    dist = distance + random.uniform(-1, 1)
    # 手部抖动参数
    tremor_amp = 1.5 + random.random() * 1.5
    tremor_freq = 8 + random.random() * 4
    # 总时长和步数（减少步数，避免轨迹被 ML 识别）
    total_ms = 500 + random.random() * 500  # 500-1000ms
    steps = 50 + random.randint(0, 30)  # 50-80 步

    log(f"  JS dispatch 拖动: start=({start_x:.1f},{start_y:.1f}) dist={dist:.1f} "
        f"steps={steps} tremor={tremor_amp:.1f}px@{tremor_freq:.0f}Hz attempt={attempt}")

    # JS 代码：在页面内执行完整的拖动流程
    # 注意：isTrusted 和 sourceCapabilities 已在 _ADVANCED_FINGERPRINT_SCRIPT（add_init_script）中提前补丁
    #       这里不再重复补丁，避免被 Baxia 检测重复补丁行为
    js_code = """
    async (params) => {
        const { startX, startY, distance, steps, tremorAmp, tremorFreq } = params;

        // 找到滑块按钮和轨道
        const btn = document.querySelector('#nc_1_n1z') || document.querySelector('.btn_slide') || document.querySelector('.nc_iconfont');
        if (!btn) return { ok: false, error: 'button not found' };

        const rect = btn.getBoundingClientRect();
        const track = document.querySelector('.nc_scale') || document.querySelector('#nc_1_n1t') || btn.parentElement;
        if (!track) return { ok: false, error: 'track not found' };

        // 辅助函数：创建并 dispatch 事件
        function dispatchEvents(target, type, clientX, clientY) {
            const opts = {
                bubbles: true, cancelable: true, composed: true,
                clientX: clientX, clientY: clientY,
                button: 0, buttons: type === 'mouseup' ? 0 : 1,
                movementX: 0, movementY: 0,
                relatedTarget: null,
                screenX: clientX, screenY: clientY
            };
            // PointerEvent
            try {
                const pe = new PointerEvent('pointer' + type, opts);
                target.dispatchEvent(pe);
            } catch(e) {}
            // MouseEvent
            const me = new MouseEvent(type, opts);
            target.dispatchEvent(me);
        }

        // mousedown
        dispatchEvents(btn, 'mousedown', startX, startY);
        await new Promise(r => setTimeout(r, 100 + Math.random() * 150));

        // mousemove 拖动
        let lastX = startX;
        const accelEnd = 0.30;  // 加速段占 30%
        for (let i = 1; i <= steps; i++) {
            const t = i / steps;

            // 非对称加速度曲线：加速快（0-30%），减速慢（30-100%）
            let eased;
            if (t < accelEnd) {
                const tt = t / accelEnd;
                eased = tt * tt * 0.5;  // 加速段，到 30% 时移动 50%
            } else {
                const tt = (t - accelEnd) / (1 - accelEnd);
                eased = 0.5 + (1 - Math.pow(1 - tt, 2.5)) * 0.5;  // 减速段
            }

            // 速度波动
            eased += Math.sin(t * Math.PI * 2.5) * 0.02;
            eased = Math.max(0, Math.min(1, eased));

            const x = startX + distance * eased;
            // Y 轴抖动（8-12Hz 正弦波 + 噪声）
            const y = startY + Math.sin(t * Math.PI * 2 * tremorFreq) * tremorAmp + (Math.random() - 0.5) * 1.5;

            dispatchEvents(document, 'mousemove', x, y);
            lastX = x;

            // 事件间隔：加速段短（5-10ms），减速段长（10-20ms）
            let baseDelay;
            if (t < accelEnd) {
                baseDelay = 5 + Math.random() * 5;
            } else {
                baseDelay = 10 + Math.random() * 10;
            }
            await new Promise(r => setTimeout(r, Math.max(3, baseDelay)));

            // 思考停顿（60-70% 处）
            if (t >= 0.6 + Math.random() * 0.1 && i === Math.floor(steps * 0.65)) {
                await new Promise(r => setTimeout(r, 100 + Math.random() * 200));
            }
        }

        // 终点微调（2-3 次）
        for (let i = 0; i < 2 + Math.floor(Math.random() * 2); i++) {
            const adjX = startX + distance + (Math.random() - 0.5) * 3;
            const adjY = startY + (Math.random() - 0.5) * 3;
            dispatchEvents(document, 'mousemove', adjX, adjY);
            await new Promise(r => setTimeout(r, 50 + Math.random() * 100));
        }

        // 释放前停顿
        await new Promise(r => setTimeout(r, 200 + Math.random() * 200));

        // mouseup
        dispatchEvents(document, 'mouseup', startX + distance, startY);

        return { ok: true, finalX: lastX };
    }
    """

    try:
        result = await frame.evaluate(js_code, {
            "startX": start_x,
            "startY": start_y,
            "distance": dist,
            "steps": steps,
            "tremorAmp": tremor_amp,
            "tremorFreq": tremor_freq,
        })
        log(f"  JS dispatch 结果: {result}")
    except Exception as e:
        log(f"  JS dispatch 失败: {type(e).__name__}: {e}")
        raise


async def bezier_mouse_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """三次贝塞尔拟人拖动（仅 page.mouse，X 近似单调递增）。

    2026-08-01 关键优化（针对 Baxia 滑块精度要求）：
    1. 距离精度：±1px 噪声（原 ±(-2,4) 会偏大 4px 导致 Baxia 判定失败）
    2. 速度曲线：慢-快-慢（模拟人类拖动节奏，Baxia 会检测匀速拖动）
    3. 终点微调：到达终点后做 2-3 次 ±1-2px 微调，模拟人类确认位置
    4. 释放前停顿：200-400ms 停顿（原 70-160ms 过短，Baxia 检测释放速度）
    5. Y 轴抖动：拖动过程中 Y 轴小幅抖动 ±1px（原 ±2px 过大）
    """
    # 距离精度：仅 ±1px 噪声（Baxia 精度要求 ±1-2px）
    dist = distance + random.uniform(-1, 1)
    sx = start_x + random.uniform(-1, 1)
    sy = start_y + random.uniform(-1, 1)
    ex = sx + dist
    ey = sy + random.uniform(-1, 1)
    # 控制点：中段轻微弧线，幅度 1~3px（原 2~6px 过大）
    amp = (1 + random.random() * 2) * (1 if random.random() > 0.5 else -1)
    c1 = (sx + dist * 0.25, sy + amp * 0.6)
    c2 = (sx + dist * 0.7, sy + amp)
    steps = 50 + random.randint(0, 15)
    log(f"  贝塞尔拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} steps={steps} attempt={attempt}")

    # 接近：先移到滑块左下方，再移到滑块上（模拟真人瞄准）
    await page.mouse.move(sx - 40 - random.random() * 30, sy + 20 + random.uniform(-10, 10), steps=8)
    await page.wait_for_timeout(120 + random.random() * 180)
    await page.mouse.move(sx - 5, sy + random.uniform(-3, 3), steps=5)
    await page.wait_for_timeout(80 + random.random() * 120)
    await page.mouse.move(sx, sy, steps=3)
    await page.wait_for_timeout(150 + random.random() * 200)
    await page.mouse.down()
    await page.wait_for_timeout(100 + random.random() * 150)

    pts = _bezier_points((sx, sy), c1, c2, (ex, ey), steps)
    last_x = sx
    for i, (x, y) in enumerate(pts):
        # 强制 X 不回退（Baxia 对回退敏感）
        if x < last_x:
            x = last_x + random.uniform(0.3, 1.0)
        # Y 轴小幅抖动 ±1px（模拟手部抖动）
        y = y + random.uniform(-1, 1)
        await page.mouse.move(x, y, steps=1)
        p = (i + 1) / steps
        # 速度曲线：慢-快-慢（0-15% 慢，15-75% 快，75-100% 慢）
        if p < 0.15:
            delay = 28 + random.random() * 22  # 起始慢 28-50ms
        elif p < 0.75:
            delay = 10 + random.random() * 18  # 中段快 10-28ms
        else:
            delay = 25 + random.random() * 35  # 末段慢 25-60ms
        await page.wait_for_timeout(delay)
        last_x = x

    # 终点微调：模拟人类确认位置（2-3 次小幅移动）
    micro_adjusts = 2 + random.randint(0, 1)
    for _ in range(micro_adjusts):
        adjust_x = ex + random.uniform(-2, 2)
        adjust_y = ey + random.uniform(-1, 1)
        await page.mouse.move(adjust_x, adjust_y, steps=1)
        await page.wait_for_timeout(40 + random.random() * 80)

    # 释放前停顿（人类会停顿确认后再释放，200-400ms）
    await page.wait_for_timeout(200 + random.random() * 200)
    await page.mouse.up()
    await page.wait_for_timeout(80 + random.random() * 120)


async def microstep_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """小步匀加速拖动：每步 2~4px，总时长约 1.2~2.2s，贴近部分真人习惯。

    2026-08-01 优化：距离精度 ±1px，释放前停顿 200-400ms，终点微调。
    """
    sx = start_x + random.uniform(-1, 1)
    sy = start_y + random.uniform(-1, 1)
    dist = distance + random.uniform(-1, 1)
    log(f"  微步拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} attempt={attempt}")
    await page.mouse.move(sx, sy, steps=5)
    await page.wait_for_timeout(150 + random.random() * 150)
    await page.mouse.down()
    await page.wait_for_timeout(100 + random.random() * 120)
    moved = 0.0
    while moved < dist:
        # 慢-快-慢曲线
        ratio = moved / dist if dist else 1
        step = 2.0 + random.random() * 2.0
        if ratio < 0.15:
            step *= 0.5  # 起始慢
        elif ratio > 0.8:
            step *= 0.6  # 末段慢
        step = min(step, dist - moved)
        moved += step
        y = sy + random.uniform(-1, 1)
        await page.mouse.move(sx + moved, y, steps=1)
        # 速度曲线：慢-快-慢
        if ratio < 0.15 or ratio > 0.8:
            await page.wait_for_timeout(25 + random.random() * 25)
        else:
            await page.wait_for_timeout(10 + random.random() * 18)
    # 终点微调
    for _ in range(2 + random.randint(0, 1)):
        await page.mouse.move(sx + dist + random.uniform(-2, 2), sy + random.uniform(-1, 1), steps=1)
        await page.wait_for_timeout(40 + random.random() * 80)
    # 释放前停顿
    await page.wait_for_timeout(200 + random.random() * 200)
    await page.mouse.up()


def close_proc_gracefully(proc: Optional[subprocess.Popen], timeout: float = 5.0) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/PID", str(proc.pid)],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        else:
            proc.terminate()
            proc.wait(timeout=timeout)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


async def get_slider_info(page) -> Optional[dict]:
    """遍历所有 frame 找滑块按钮与可拖距离。

    距离优先用 JS 精测：轨道右缘 - 按钮右缘（更贴近 Baxia 判定的“到最右边”）。
    """
    for frame in page.frames:
        for sel in SLIDER_BUTTON_SELECTORS:
            try:
                button = await frame.query_selector(sel)
                if not button:
                    continue
                box = await button.bounding_box()
                if not box or box.get("width", 0) <= 0:
                    continue

                # JS 精测可拖距离
                dist_js = None
                try:
                    dist_js = await frame.evaluate(
                        """(btnSel) => {
                          const btn = document.querySelector(btnSel)
                            || document.querySelector('#nc_1_n1z')
                            || document.querySelector('.btn_slide');
                          if (!btn) return null;
                          const track = document.querySelector('.nc_scale')
                            || document.querySelector('#nc_1_n1t')
                            || document.querySelector('.scale_text')
                            || btn.parentElement;
                          if (!track) return null;
                          const br = btn.getBoundingClientRect();
                          const tr = track.getBoundingClientRect();
                          // 需要把按钮左边拖到轨道右边内侧
                          const d = (tr.right - br.right);
                          return d > 20 ? d : (tr.width - br.width);
                        }""",
                        sel,
                    )
                except Exception:
                    dist_js = None

                track_width = float(dist_js) if dist_js and float(dist_js) > 20 else None
                if track_width is None:
                    track_width = 260.0
                    for tsel in SLIDER_TRACK_SELECTORS:
                        try:
                            track = await frame.query_selector(tsel)
                            if not track:
                                continue
                            track_box = await track.bounding_box()
                            if track_box and track_box.get("width", 0) > 0:
                                track_width = float(track_box["width"] - box["width"])
                                break
                        except Exception:
                            pass

                # 常见轨道可拖区间约 200~320
                track_width = max(200.0, min(float(track_width), 340.0))
                return {
                    "button": button,
                    "frame": frame,
                    "x": float(box["x"] + box["width"] / 2),
                    "y": float(box["y"] + box["height"] / 2),
                    "distance": track_width,
                    "width": float(box["width"]),
                    "height": float(box["height"]),
                }
            except Exception:
                continue
    return None


async def detect_captcha_container(page) -> tuple[bool, Optional[str]]:
    for selector in BAXIA_CONTAINER_SELECTORS:
        try:
            elem = await page.query_selector(selector)
            if elem and await elem.is_visible():
                return True, selector
        except Exception:
            pass
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        for selector in BAXIA_CONTAINER_SELECTORS:
            try:
                elem = await frame.query_selector(selector)
                if elem and await elem.is_visible():
                    return True, selector
            except Exception:
                pass
    return False, None


# 2026-08-01 新增：Baxia 配置探针（增强版）
# 目标：从 Baxia iframe 中提取验证所需的关键参数，
#       为"直接调用 Baxia 验证 API 获取 x5sec"方案提供数据支持。
# 关键发现（线上日志分析）：
#   - x5secdata 在 punish URL 的查询参数中（不在 window._config_）
#   - Baxia 数据存储在 window.__baxia__（BAXIA_KEY），不是 window._config_
#   - NoCaptcha 组件实例可能存储在 window.NoCaptcha 或 AWSC.nvc
# 关键字段（来自 https://blog.csdn.net/zhengjianyang1/article/details/148844383）：
#   - pp: 用于 bx-pp 加密（WASM）
#   - ppModule: WASM 模块
#   - x5secdata / SECDATA: 页面返回的验证数据（在 punish URL 中）
#   - appkey / scene: 应用标识
_BAXIA_CONFIG_PROBE_JS = r"""
(() => {
  const result = {};
  const truncate = (v, max=120) => {
    const s = String(v);
    return s.length > max ? s.substring(0, max) + '...(len=' + s.length + ')' : s;
  };
  try {
    result.url = location.href;
    // 1. 从 URL 查询参数中提取 x5secdata（关键！线上日志证实 x5secdata 在 URL 中）
    try {
      const u = new URL(location.href);
      const x5secdata = u.searchParams.get('x5secdata');
      if (x5secdata) result.x5secdata = truncate(x5secdata, 200);
      const x5step = u.searchParams.get('x5step');
      if (x5step) result.x5step = x5step;
      const action = u.searchParams.get('action');
      if (action) result.action = action;
    } catch (e) { result.urlParseErr = e.message; }

    // 2. 检查 window._config_（旧版 Baxia 配置）
    try {
      const cfg = window._config_ || {};
      const fields = ['pp', 'ppModule', 'ppt', 'appkey', 'scene', 'x5secdata', 'SECDATA',
                      'slideData', 'token', 'sessionId', 'sig', 'x5Step'];
      for (const k of fields) {
        if (cfg[k] !== undefined && cfg[k] !== null && cfg[k] !== '') {
          result['cfg_' + k] = truncate(cfg[k]);
        }
      }
      result.cfg_allKeys = Object.keys(cfg).join(',').substring(0, 200);
    } catch (e) {}

    // 3. 检查 window.__baxia__（BAXIA_KEY，baxiaCommon.js 中定义的存储键）
    try {
      const bx = window.__baxia__ || {};
      const bxKeys = Object.keys(bx);
      result.baxia_keys = bxKeys.join(',').substring(0, 300);
      // 提取关键字段
      for (const k of ['appkey', 'scene', 'token', 'sessionId', 'sig', 'data',
                       'pp', 'ppModule', 'slideData', 'x5secdata', 'SECDATA',
                       'nc', 'nvc', 'verifyFn', 'checkParams']) {
        if (bx[k] !== undefined && bx[k] !== null) {
          result['bx_' + k] = truncate(bx[k]);
        }
      }
      // 检查 __baxia__ 中的对象类型字段，记录其方法名
      for (const k of bxKeys) {
        if (typeof bx[k] === 'object' && bx[k] !== null) {
          try {
            const subKeys = Object.keys(bx[k]).join(',').substring(0, 150);
            if (subKeys) result['bx_obj_' + k] = subKeys;
          } catch (e) {}
        }
      }
    } catch (e) { result.baxiaErr = e.message; }

    // 4. 检查 NoCaptcha 全局对象
    try {
      result.NoCaptcha = typeof window.NoCaptcha;
      if (window.NoCaptcha) {
        result.NoCaptchaKeys = Object.keys(window.NoCaptcha).join(',').substring(0, 200);
        // 检查 NoCaptcha 实例方法
        const nc = window.NoCaptcha;
        if (nc.prototype) {
          result.NoCaptchaProto = Object.getOwnPropertyNames(nc.prototype).join(',').substring(0, 200);
        }
      }
    } catch (e) { result.NoCaptcha = 'ERR:' + e.message; }

    // 5. 检查 AWSC 全局对象（Alibaba Security Center）
    try {
      result.AWSC = typeof window.AWSC;
      if (window.AWSC) {
        result.AWSC_keys = Object.keys(window.AWSC).join(',').substring(0, 200);
        // AWSC.nvc 是 NoCaptcha 验证组件
        if (window.AWSC.nvc) {
          result.AWSC_nvc = typeof window.AWSC.nvc;
          result.AWSC_nvc_keys = Object.keys(window.AWSC.nvc).join(',').substring(0, 150);
        }
      }
    } catch (e) { result.AWSC = 'ERR:' + e.message; }

    // 6. 搜索所有 window 上的 baxia/bx/nvc 相关全局变量
    try {
      const related = [];
      for (const k of Object.getOwnPropertyNames(window)) {
        const kl = k.toLowerCase();
        if (kl.includes('baxia') || kl.includes('nvc') || kl === 'bx' ||
            kl.startsWith('bx_') || kl.startsWith('_bx') || kl.startsWith('__bx')) {
          try {
            const v = window[k];
            const t = typeof v;
            if (t === 'function' || t === 'object') {
              related.push(k + ':' + t);
            }
          } catch (e) {}
        }
      }
      if (related.length) result.baxiaGlobals = related.join(' | ').substring(0, 400);
    } catch (e) {}
  } catch (e) {
    result.error = e.message;
  }
  return result;
})()
"""


async def log_baxia_config(page) -> dict:
    """从 Baxia iframe 中提取验证所需的关键参数，记录到日志。

    在 Baxia iframe 内执行 JS 探针，提取：
    - x5secdata（从 punish URL 查询参数）
    - window.__baxia__ 中的验证参数
    - NoCaptcha / AWSC 组件状态
    这些参数用于"直接调用 Baxia 验证 API 获取 x5sec"方案。
    """
    try:
        # 先在主页面执行
        try:
            result = await page.evaluate(_BAXIA_CONFIG_PROBE_JS)
            if result and (result.get("x5secdata") or result.get("baxia_keys") or
                           result.get("NoCaptcha") != "undefined" or result.get("AWSC") != "undefined"):
                log(f"🔍 [Baxia配置-主页] {json.dumps(result, ensure_ascii=False)}")
                return result
        except Exception:
            pass

        # 在 Baxia/punish iframe 内执行（优先 punish URL，因为 x5secdata 在那里）
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            fu = (frame.url or "").lower()
            if "baxia" in fu or "punish" in fu or "nocaptcha" in fu or "captcha" in fu or "_____tmd_____" in fu:
                try:
                    result = await frame.evaluate(_BAXIA_CONFIG_PROBE_JS)
                    if result:
                        log(f"🔍 [Baxia配置-iframe] {json.dumps(result, ensure_ascii=False)}")
                        return result
                except Exception as e:
                    log(f"🔍 [Baxia配置-iframe] 执行失败: {e}")

        # 遍历所有 frame 兜底（punish URL 可能不含上述关键字）
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            fu = (frame.url or "")
            if "x5secdata" in fu:
                try:
                    result = await frame.evaluate(_BAXIA_CONFIG_PROBE_JS)
                    if result and result.get("x5secdata"):
                        log(f"🔍 [Baxia配置-x5secdata帧] {json.dumps(result, ensure_ascii=False)}")
                        return result
                except Exception as e:
                    log(f"🔍 [Baxia配置-x5secdata帧] 执行失败: {e}")

        log(f"🔍 [Baxia配置] 未找到含 x5secdata 的 iframe 或 Baxia 组件未初始化")
        return {}
    except Exception as e:
        log(f"🔍 [Baxia配置] 提取失败: {e}")
        return {}


async def check_solved(page) -> bool:
    # 2026-08-01 诊断增强：记录每个选择器的检测结果，定位失败原因
    found_success = []
    found_fail = []
    for sel in SUCCESS_SELECTORS:
        for frame in page.frames:
            try:
                elem = await frame.query_selector(sel)
                if elem and await elem.is_visible():
                    found_success.append(sel)
            except Exception:
                pass
    if found_success:
        log(f"  check_solved: ✓ 命中成功选择器 {found_success}")
        return True
    for sel in FAIL_SELECTORS:
        for frame in page.frames:
            try:
                elem = await frame.query_selector(sel)
                if elem and await elem.is_visible():
                    found_fail.append(sel)
            except Exception:
                pass
    if found_fail:
        log(f"  check_solved: × 命中失败选择器 {found_fail}")
        return False
    # 2026-08-01 诊断：转储 baxia iframe 内的 slider 元素 class，定位状态
    try:
        for frame in page.frames:
            if "baxia" in (frame.url or "") or "punish" in (frame.url or ""):
                cls_info = await frame.evaluate(
                    """() => {
                      const btn = document.querySelector('#nc_1_n1z, .btn_slide, .nc_iconfont, .nc-lang-cnt');
                      const track = document.querySelector('.nc_scale, .scale_text, .nc-lang');
                      return {
                        btnClass: btn ? btn.className : null,
                        btnDisplay: btn ? getComputedStyle(btn).display : null,
                        trackClass: track ? track.className : null,
                        bodyText: document.body ? document.body.innerText.substring(0, 200) : '',
                      };
                    }"""
                )
                if cls_info:
                    log(f"  check_solved: 诊断 baxia frame: {cls_info}")
                # 2026-08-01 新增：提取 Baxia 配置（window._config_），分析 x5sec 获取流程
                try:
                    await log_baxia_config(page)
                except Exception:
                    pass
                break
    except Exception:
        pass
    detected, _ = await detect_captcha_container(page)
    log(f"  check_solved: 无成功/失败选择器，容器检测={detected} → {'未通过' if detected else '通过'}")
    return not detected


async def human_like_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """容器内拖动：接近轨迹 + 起点偏移 + 三阶段速度 + Y 弧线 + 终点微调。

    2026-08-01 优化：
    1. 距离精度：±1px 噪声（原无精度控制）
    2. 移除过冲 overshoot（原 6-16px 过冲导致 Baxia 判定失败）
    3. Y 抖动 ±1px（原 ±5px 过大）
    4. 释放前停顿 200-400ms
    5. 起点偏移 ±2px（原 ±4px 过大）
    """
    # 距离精度：仅 ±1px 噪声
    dist = distance + random.uniform(-1, 1)
    if attempt == 1:
        steps_base, step_delay_min, step_delay_max = 38, 28, 65
        pause_points = [0.35 + random.random() * 0.2]
    elif attempt == 2:
        steps_base, step_delay_min, step_delay_max = 42, 35, 80
        pause_points = []
    elif attempt == 3:
        steps_base, step_delay_min, step_delay_max = 32, 20, 50
        pause_points = []
    elif attempt == 4:
        steps_base, step_delay_min, step_delay_max = 48, 45, 95
        pause_points = [0.4 + random.random() * 0.2]
    else:
        steps_base = 36 + random.randint(0, 12)
        step_delay_min = 25 + random.randint(0, 20)
        step_delay_max = step_delay_min + 30 + random.randint(0, 30)
        pause_points = []

    steps = steps_base + random.randint(0, 10)
    pause_duration_ms = 220 + random.randint(0, 180)
    log(
        f"拖动策略: attempt={attempt}, steps={steps}, "
        f"delay={step_delay_min}-{step_delay_max}ms, pauses={len(pause_points)}"
    )

    # 起点在按钮中心附近随机偏移（±2px）
    actual_start_x = start_x + random.uniform(-2, 2)
    actual_start_y = start_y + random.uniform(-1, 1)

    # 接近轨迹：从按钮附近随机点移入，而非瞬移
    approach_angle = random.uniform(0, 2 * math.pi)
    approach_dist = 40 + random.random() * 80
    approach_x = max(5, min(WINDOW_WIDTH - 5, actual_start_x + math.cos(approach_angle) * approach_dist))
    approach_y = max(5, min(WINDOW_HEIGHT - 5, actual_start_y + math.sin(approach_angle) * approach_dist))
    approach_steps = 8 + random.randint(0, 8)
    await page.mouse.move(approach_x, approach_y)
    await page.wait_for_timeout(80 + random.randint(0, 120))
    for i in range(1, approach_steps + 1):
        t = i / approach_steps
        eased = t * t * (3 - 2 * t)
        mx = approach_x + (actual_start_x - approach_x) * eased
        my = approach_y + (actual_start_y - approach_y) * eased
        await page.mouse.move(mx, my)
        await page.wait_for_timeout(12 + random.random() * 25)

    await page.wait_for_timeout(100 + random.random() * 180)
    await page.mouse.down()
    await page.wait_for_timeout(90 + random.random() * 120)
    # 按下后微漂移
    await page.mouse.move(
        actual_start_x + random.uniform(-1, 1),
        actual_start_y + random.uniform(-1, 1),
    )
    await page.wait_for_timeout(40 + random.random() * 60)

    arc_direction = -1 if random.random() < 0.5 else 1
    arc_amplitude = 1 + random.random() * 2  # 弧线幅度 1-3px（原 3-9px 过大）
    last_x = actual_start_x
    last_y = actual_start_y
    pause_idx = 0

    for i in range(1, steps + 1):
        progress = i / steps
        if progress < 0.18:
            speed_weight = 1.0 - 0.65 * (progress / 0.18)
        elif progress < 0.72:
            speed_weight = 0.22 + 0.12 * math.sin(progress * math.pi * 5)
        else:
            speed_weight = 0.35 + 0.65 * ((progress - 0.72) / 0.28)

        # ease-in-out 变体
        eased = (progress ** 2.3) / ((progress ** 2.3) + ((1 - progress) ** 2.3) + 1e-9)
        target_x = actual_start_x + dist * eased

        # 强制 X 不回退（Baxia 对回退敏感）
        if target_x < last_x:
            target_x = last_x + random.uniform(0.3, 1.0)

        arc_offset = arc_direction * arc_amplitude * math.sin(math.pi * progress)
        y_drift = (random.random() - 0.5) * 2  # Y 抖动 ±1px（原 ±2.5px）
        target_y = actual_start_y + arc_offset
        current_y = last_y * 0.55 + target_y * 0.45 + y_drift

        await page.mouse.move(target_x, current_y)

        median_delay = step_delay_min + (step_delay_max - step_delay_min) * 0.4
        # Box-Muller 对数正态间隔
        u1 = max(1e-10, random.random())
        u2 = random.random()
        normal = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
        log_delay = median_delay * math.exp(0.45 * normal)
        delay = max(step_delay_min, min(step_delay_max * 2.2, log_delay)) * speed_weight
        await page.wait_for_timeout(delay)

        last_x, last_y = target_x, current_y
        if pause_idx < len(pause_points) and progress >= pause_points[pause_idx]:
            log(f"  在 progress={progress:.2f} 处停顿 {pause_duration_ms}ms")
            await page.wait_for_timeout(pause_duration_ms)
            pause_idx += 1

    # 终点微调（移除原过冲 overshoot，直接微调）
    await page.wait_for_timeout(40 + random.random() * 80)
    for _ in range(2 + random.randint(0, 1)):
        await page.mouse.move(
            actual_start_x + dist + random.uniform(-2, 2),
            actual_start_y + random.uniform(-1, 1),
            steps=1,
        )
        await page.wait_for_timeout(40 + random.random() * 80)
    # 释放前停顿（200-400ms）
    await page.wait_for_timeout(200 + random.random() * 200)
    await page.mouse.up()
    await page.wait_for_timeout(80 + random.random() * 120)


async def human_like_drag_out_of_container(
    page, start_x: float, start_y: float, distance: float, attempt: int = 1
) -> None:
    """出容器拖动：Y 适度偏出弹窗（±10~25px），模拟真人不拘束手部路径。

    2026-08-01 优化：
    1. 距离精度：±1px 噪声
    2. Y 偏移控制在 ±25px 内（原 ±55-125px 过大，Baxia 会判定机器人）
    3. 移除过冲 overshoot（原 5-17px 过冲）
    4. Y 抖动 ±1px（原 ±5px）
    5. 释放前停顿 200-400ms
    """
    # 距离精度：仅 ±1px 噪声
    dist = distance + random.uniform(-1, 1)
    if attempt <= 2:
        steps_base, step_delay_min, step_delay_max = 40, 28, 70
    elif attempt == 3:
        steps_base, step_delay_min, step_delay_max = 34, 22, 55
    else:
        steps_base = 38 + random.randint(0, 12)
        step_delay_min = 25 + random.randint(0, 25)
        step_delay_max = step_delay_min + 30 + random.randint(0, 40)

    steps = steps_base + random.randint(0, 10)
    log(f"  超出容器拖动策略: attempt={attempt}, steps={steps}, delay={step_delay_min}-{step_delay_max}ms")

    actual_start_x = start_x + random.uniform(-1, 1)
    actual_start_y = start_y + random.uniform(-1, 1)

    await page.mouse.move(actual_start_x - 30 - random.random() * 40, actual_start_y + random.uniform(-10, 10))
    await page.wait_for_timeout(80 + random.random() * 120)
    await page.mouse.move(actual_start_x, actual_start_y, steps=6)
    await page.wait_for_timeout(100 + random.random() * 150)
    await page.mouse.down()
    await page.wait_for_timeout(90 + random.random() * 110)

    # Y 偏移拐点：控制在 ±25px 内（原 ±55-125px）
    num_out_points = 2 + random.randint(0, 1)
    out_points = []
    for i in range(num_out_points):
        prog = 0.2 + (0.6 * (i + 1) / (num_out_points + 1)) + random.uniform(-0.05, 0.05)
        direction = -1 if i % 2 == 0 else 1
        magnitude = 10 + random.random() * 15  # 10-25px（原 55-125px）
        out_points.append({"progress": max(0.15, min(0.85, prog)), "y_offset": direction * magnitude})
    log(
        "  出容器拐点: "
        + " | ".join(f"p={p['progress']:.2f},y={p['y_offset']:.0f}px" for p in out_points)
    )

    last_x = actual_start_x
    for i in range(1, steps + 1):
        progress = i / steps
        eased = progress * progress * (3 - 2 * progress)
        target_x = actual_start_x + dist * eased
        # 强制 X 不回退
        if target_x < last_x:
            target_x = last_x + random.uniform(0.3, 1.0)

        base_arc = math.sin(math.pi * progress) * 2  # 基础弧线 2px（原 5px）
        y_offset = 0.0
        for op in out_points:
            d = abs(progress - op["progress"])
            if d < 0.18:
                influence = math.exp(-(d * d) / (2 * 0.055 * 0.055))
                y_offset += op["y_offset"] * influence
        current_y = actual_start_y + base_arc + y_offset + random.uniform(-1, 1)  # Y 抖动 ±1px
        await page.mouse.move(target_x, current_y)

        bell = math.sin(math.pi * progress)
        delay_weight = 1 - bell * 0.45
        delay = (step_delay_min + random.random() * (step_delay_max - step_delay_min)) * delay_weight
        await page.wait_for_timeout(delay)
        last_x = target_x

    # 终点微调（移除原过冲 overshoot）
    await page.wait_for_timeout(40 + random.random() * 80)
    for _ in range(2 + random.randint(0, 1)):
        await page.mouse.move(
            actual_start_x + dist + random.uniform(-2, 2),
            actual_start_y + random.uniform(-1, 1),
            steps=1,
        )
        await page.wait_for_timeout(40 + random.random() * 80)
    # 释放前停顿（200-400ms）
    await page.wait_for_timeout(200 + random.random() * 200)
    await page.mouse.up()
    await page.wait_for_timeout(80 + random.random() * 120)


async def wait_for_slider_ready(page, max_wait_ms: int = 10000) -> Optional[dict]:
    start = time.time()
    last_log = 0.0
    while (time.time() - start) * 1000 < max_wait_ms:
        # 登录页
        url = (page.url or "").lower()
        if "login.taobao.com" in url or "login.goofish.com" in url or "/login" in url:
            return {"is_login_page": True}

        if await check_solved(page):
            # 可能用户手动完成，或本就无需验证
            detected, _ = await detect_captcha_container(page)
            if not detected:
                return {"already_solved": True}

        info = await get_slider_info(page)
        if info:
            return info

        now = time.time()
        if now - last_log > 2.0:
            elapsed = int((now - start) * 1000)
            log(f"  等待滑块... ({elapsed}ms/{max_wait_ms}ms)")
            last_log = now
        await asyncio.sleep(0.4)
    return None


async def diagnose_frames(page) -> None:
    log(f"页面 URL: {page.url}")
    for i, frame in enumerate(page.frames):
        try:
            furl = frame.url or ""
            tag = "[PUNISH]" if ("punish" in furl or "_____tmd_____" in furl) else "[OK]"
            log(f"  Frame {i}: {tag} {furl[:180]}")
        except Exception:
            pass


async def close_captcha_dialog(page) -> bool:
    close_selectors = [
        ".nc_close",
        ".nc-icon-close",
        ".baxia-close",
        ".dialog-close",
        ".modal-close",
        ".popup-close",
        ".close-btn",
        ".btn-close",
        ".ant-modal-close",
        ".next-dialog-close",
        'button[aria-label*="close"]',
        'button[aria-label*="关闭"]',
    ]
    search_frames = [page.main_frame] + [f for f in page.frames if f != page.main_frame]
    for f in search_frames:
        for sel in close_selectors:
            try:
                elem = await f.query_selector(sel)
                if elem and await elem.is_visible():
                    log(f"找到弹窗关闭按钮: {sel}")
                    await elem.click(timeout=2000)
                    await asyncio.sleep(0.8)
                    return True
            except Exception:
                pass
        try:
            closed = await f.evaluate(
                """() => {
                const candidates = [];
                const allElems = document.querySelectorAll('button, [role="button"], a, span, div, i');
                for (const el of Array.from(allElems)) {
                  const text = (el.textContent || '').trim();
                  const aria = el.getAttribute('aria-label') || '';
                  const cls = typeof el.className === 'string' ? el.className : '';
                  if (/^[×✕✗xX]$/.test(text) || /关闭|close/i.test(aria) || /close|关闭/i.test(cls)) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.width < 60 && rect.height > 0 && rect.height < 60) {
                      candidates.push(el);
                    }
                  }
                }
                candidates.sort((a, b) => {
                  const ra = a.getBoundingClientRect(), rb = b.getBoundingClientRect();
                  return (rb.right - ra.right) || (ra.top - rb.top);
                });
                if (candidates.length) { candidates[0].click(); return true; }
                return false;
            }"""
            )
            if closed:
                log("通过文本特征点击了弹窗关闭按钮")
                await asyncio.sleep(0.8)
                return True
        except Exception:
            pass
    log("未找到弹窗关闭按钮")
    return False


def _is_punish_url(url: str) -> bool:
    """检测是否为 Baxia punish URL（来自商品关键词搜索触发风控）。

    punish URL 是搜索触发 FAIL_SYS_USER_VALIDATE 时由 MTOP 返回的验证页 URL，
    典型特征：URL 中含 "punish" 或 "_____tmd_____"。
    这类 URL 来自搜索上下文，直接 goto 即可触发滑块，
    不应走 /im 消息页拟人导航（会偏离搜索验证场景）。
    """
    if not url:
        return False
    url_lower = url.lower()
    return "punish" in url_lower or "_____tmd_____" in url_lower


async def _navigate_to_target(page, target_url: str) -> tuple:
    """根据目标 URL 类型选择导航策略。

    - punish URL（搜索上下文）：直接 goto，不走拟人 /im 导航。
      搜索场景的滑块求解应直接访问 punish URL，避免 /im 导航偏离验证上下文。
      （注：goofishSearch.py 的搜索流程已不再求解滑块，但本函数仍保留 punish URL 直跳能力，
      供未来可能的其他场景使用。）
    - 其他 URL（消息页上下文）：使用 human_warmup_and_enter_im 拟人导航

    返回 (page, actual_url)：actual_url 供后续 navigate_fresh 重用。
    """
    if _is_punish_url(target_url):
        log(f"检测到 Baxia punish URL（搜索上下文），直接访问: {target_url[:100]}...")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            log(f"跳转 punish URL 失败: {e}")
        # 等待滑块渲染（Baxia punish 页 JS 需要时间初始化滑块组件）
        await asyncio.sleep(1.5)
        return page, target_url
    else:
        return await human_warmup_and_enter_im(page, target_url or DEFAULT_TARGET_URL)


async def navigate_fresh(page, target_url: str, *, hard: bool = False) -> tuple:
    """重置导航。

    hard=False（默认）：不清 localStorage/sessionStorage，避免把登录痕迹一并清掉加重风控。
    hard=True：清 storage 后再进入目标页（仅在加载失败连跪时使用）。

    返回 (page, actual_url)：actual_url 供后续刷新复用。
    根据 target_url 类型自动选择导航策略：
    - punish URL（搜索上下文）：直接 goto
    - 其他 URL（消息页上下文）：human_warmup_and_enter_im 拟人导航
    """
    if hard:
        try:
            await page.evaluate(
                """() => {
                try { localStorage.clear(); } catch(e) {}
                try { sessionStorage.clear(); } catch(e) {}
            }"""
            )
            log("已清理 localStorage/sessionStorage（hard）")
        except Exception as e:
            log(f"清理存储失败(可忽略): {e}")

    # 根据目标 URL 类型选择导航策略
    try:
        page, actual_url = await _navigate_to_target(page, target_url or DEFAULT_TARGET_URL)
        return page, actual_url
    except Exception:
        target_wait = 2.0 + random.random() * 1.8
        try:
            await page.goto(target_url or DEFAULT_TARGET_URL, wait_until="domcontentloaded", timeout=45000)
            log(f"已导航到目标页，等待 {target_wait:.1f}s 让页面加载")
            await asyncio.sleep(target_wait)
        except Exception as e:
            log(f"导航到目标页失败: {e}")
        return page, target_url or DEFAULT_TARGET_URL


async def click_retry_if_needed(page) -> bool:
    """验证失败后点击框体重试。"""
    for frame in page.frames:
        try:
            text = await frame.evaluate(
                "() => document.body ? document.body.innerText : ''"
            )
            if not text:
                continue
            if not any(
                k in text
                for k in (
                    "验证失败",
                    "点击框体重试",
                    "点击重试",
                    "滑块加载失败",
                    "滑动失败",
                    "验证未通过",
                )
            ):
                continue
            for sel in ("#nc_1", ".nc_wrapper", "#baxia-dialog", ".nc-lang-cnt", ".errloading", "#nc_1_refresh1"):
                try:
                    elem = await frame.query_selector(sel)
                    if elem and await elem.is_visible():
                        await elem.click(timeout=2000)
                        log(f"已点击重试区域: {sel}")
                        await asyncio.sleep(2.2)
                        return True
                except Exception:
                    pass
            # 点击弹窗中心
            try:
                box = await frame.evaluate(
                    """() => {
                    const el = document.querySelector('#nc_1, .nc_wrapper, #baxia-dialog, .slide-verify');
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return {x: r.x + r.width/2, y: r.y + r.height/2};
                }"""
                )
                if box:
                    await page.mouse.click(box["x"], box["y"])
                    log("已点击弹窗中心触发重试")
                    await asyncio.sleep(2.2)
                    return True
            except Exception:
                pass
        except Exception:
            continue
    return False


async def page_shows_load_failure(page) -> bool:
    """检测消息页/会话页「加载失败」风控态（人工拖也过不了的典型表现）。"""
    # 2026-08-03 修复"假成功"：浏览器错误页（chrome-error:// / chromewebdata，ERR_TIMED_OUT 等）
    # document.body 为空，page.evaluate 抛异常会被下方 except 吞掉返回 False，
    # 导致错误页被误判为正常页面 → 后续"未检测到滑块→验证通过"假成功。
    # 因此先检查 URL，错误页直接视为加载失败。
    url_l = (page.url or "").lower()
    if "chrome-error://" in url_l or "chromewebdata" in url_l:
        return True
    try:
        text = await page.evaluate(
            "() => document.body ? document.body.innerText.slice(0, 800) : ''"
        )
        if not text:
            return False
        return bool(
            any(
                k in text
                for k in (
                    "加载失败",
                    "下载消息失败",
                    "网络异常",
                    "请刷新页面",
                    "连接中断",
                    "系统繁忙",
                )
            )
        )
    except Exception:
        return False


async def human_mouse_move_to(page, target_x: float, target_y: float, *, approach: bool = True) -> None:
    """真人鼠标移动到目标点（贝塞尔曲线 + 犹豫 + 微过冲）。

    模拟真人从当前位置移动到目标点的轨迹：
    - 贝塞尔曲线（非直线）
    - 中段轻微减速（犹豫）
    - 接近终点时微过冲再回退
    - 每步随机延迟（对数正态分布）
    """
    # 获取当前鼠标位置（近似：用上次记录或随机起点）
    # Playwright 没有获取当前位置的 API，用随机起点模拟
    if approach:
        # 从目标点附近随机起点接近（模拟真人从某处移过来）
        angle = random.uniform(0, 2 * math.pi)
        dist = 200 + random.random() * 300
        start_x = max(5, min(WINDOW_WIDTH - 5, target_x + math.cos(angle) * dist))
        start_y = max(5, min(WINDOW_HEIGHT - 5, target_y + math.sin(angle) * dist))
    else:
        start_x = target_x + random.uniform(-50, 50)
        start_y = target_y + random.uniform(-50, 50)

    # 贝塞尔控制点：制造弧线
    mid_x = (start_x + target_x) / 2
    mid_y = (start_y + target_y) / 2
    arc_amp = (20 + random.random() * 40) * (1 if random.random() > 0.5 else -1)
    c1 = (start_x + (target_x - start_x) * 0.3, start_y + (target_y - start_y) * 0.1 + arc_amp * 0.5)
    c2 = (start_x + (target_x - start_x) * 0.7, start_y + (target_y - start_y) * 0.9 + arc_amp)

    steps = 25 + random.randint(0, 15)
    pts = _bezier_points((start_x, start_y), c1, c2, (target_x, target_y), steps)

    for i, (x, y) in enumerate(pts):
        await page.mouse.move(x, y, steps=1)
        p = (i + 1) / steps
        # 中段减速（犹豫），两端稍快
        delay = 8 + random.random() * 20
        if 0.3 < p < 0.7:
            delay *= 1.6
        await page.wait_for_timeout(delay)

    # 微过冲再回退到目标
    overshoot = 3 + random.random() * 6
    await page.mouse.move(target_x + overshoot, target_y + random.uniform(-2, 2), steps=2)
    await page.wait_for_timeout(30 + random.random() * 60)
    await page.mouse.move(target_x, target_y, steps=2)
    await page.wait_for_timeout(40 + random.random() * 80)


async def human_mouse_click(page, x: float, y: float) -> None:
    """真人鼠标点击：移动到目标 → 停顿 → 按下 → 微停 → 抬起。"""
    await human_mouse_move_to(page, x, y)
    # 悬停停顿（真人看准目标后停顿一下再点）
    await page.wait_for_timeout(80 + random.random() * 180)
    await page.mouse.down()
    # 按下持续时间（真人 50-150ms）
    await page.wait_for_timeout(50 + random.random() * 100)
    await page.mouse.up()
    await page.wait_for_timeout(30 + random.random() * 60)


async def human_warmup_and_enter_im(page, target_url: str):
    """拟人路径进入消息页：首页闲逛 → 真人鼠标点击消息入口，避免直接 goto /im 触发反爬。

    关键改进（基于实测：真人从首页点击消息入口一次通过，直接访问 /im 被风控）：
    1. 首页用贝塞尔曲线鼠标移动（非直线）
    2. 点击前先 hover（触发 mouseover），再用真人鼠标点击（move + down + up）
    3. 点击后轮询 URL 变化或 popup（不用 expect_popup，避免同窗口 SPA 跳转误判超时）
    4. 真人鼠标点击失败时，用 locator.click() 备选（确保点击到正确元素）
    5. 记录带 spm 参数的 URL，后续刷新都用这个 URL

    返回 (page, actual_im_url)：actual_im_url 是带 spm 参数的消息页 URL。
    """
    home = "https://www.goofish.com/"
    log(f"拟人导航：先打开首页 {home}")
    try:
        await page.goto(home, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"首页加载警告: {e}")

    # 等待首页侧边栏渲染完成
    await asyncio.sleep(2.0 + random.random() * 1.5)

    # 首页真人鼠标晃动（贝塞尔曲线，非直线）+ 轻微滚动
    for _ in range(3 + random.randint(0, 3)):
        x = 120 + random.random() * (WINDOW_WIDTH - 240)
        y = 100 + random.random() * (WINDOW_HEIGHT - 200)
        await human_mouse_move_to(page, x, y, approach=True)
        await asyncio.sleep(0.15 + random.random() * 0.35)
    try:
        await page.mouse.wheel(0, 200 + random.randint(0, 400))
    except Exception:
        pass
    await asyncio.sleep(1.2 + random.random() * 1.8)

    # 查找「消息」入口元素，返回 boundingBox
    async def _find_msg_entry_bbox() -> Optional[dict]:
        """查找消息入口元素，选面积最小的候选（最精确匹配）。"""
        return await page.evaluate(
            """() => {
            // 扩大选择器范围，覆盖闲鱼首页侧边栏各种命名约定
            const candidates = [];
            const selectors = [
                '[class*="sidebar-item"]', '[class*="side-item"]', '[class*="nav-item"]',
                '[class*="menu-item"]', '[class*="entry-item"]', '[class*="bar-item"]',
                'aside a', 'aside li', 'nav a', 'nav li', '[role="link"]', '[role="menuitem"]',
                '[class*="sidebar"] a', '[class*="sidebar"] li', '[class*="sidebar"] div'
            ];
            selectors.forEach(sel => {
                try { document.querySelectorAll(sel).forEach(el => {
                    const t = (el.textContent || '').trim();
                    if (t.includes('消息') && t.length < 30) candidates.push(el);
                }); } catch(e) {}
            });
            // 选面积最小的元素（最精确匹配"消息"入口，避免选到外层容器）
            let best = null;
            let bestArea = Infinity;
            for (const el of candidates) {
                const r = el.getBoundingClientRect();
                if (r.width <= 0 || r.height <= 0) continue;
                const area = r.width * r.height;
                if (area < bestArea) { bestArea = area; best = el; }
            }
            if (!best) return null;
            best.scrollIntoView({block:'center'});
            const r = best.getBoundingClientRect();
            return {
                x: r.left + r.width / 2,
                y: r.top + r.height / 2,
                width: r.width,
                height: r.height,
                text: (best.textContent||'').trim().substring(0, 20),
            };
        }"""
        )

    # 检测是否有新 popup 打开（返回 popup page 或 None）
    def _find_im_popup():
        try:
            for p in page.context.pages:
                if p != page and "/im" in (p.url or ""):
                    return p
        except Exception:
            pass
        return None

    # 为目标页面（popup 或同窗口跳转页）注入指纹修复脚本
    async def _fix_fingerprint_and_return(target_page, actual_url: str, tag: str):
        if _USING_PATCHRIGHT:
            try:
                await target_page.add_init_script(_ADVANCED_FINGERPRINT_SCRIPT)
            except Exception:
                pass
            try:
                await target_page.evaluate(_ADVANCED_FINGERPRINT_SCRIPT)
                fix = await target_page.evaluate(
                    "() => ({ chrome: !!(window.chrome && window.chrome.runtime), languages: navigator.languages })"
                )
                log(f"{tag} 指纹修复结果: {fix}")
            except Exception as e:
                log(f"{tag} 指纹修复异常: {e}")
        await asyncio.sleep(2.0 + random.random() * 1.5)
        return target_page, actual_url

    # 轮询等待 URL 变化或 popup（同时处理同窗口 SPA 跳转和新窗口 popup）
    async def _wait_for_im_navigation(old_url: str, timeout_s: float, tag: str):
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            await asyncio.sleep(0.3)
            # 检查 popup（新窗口）
            popup = _find_im_popup()
            if popup:
                try:
                    await popup.wait_for_load_state("domcontentloaded", timeout=30000)
                except Exception:
                    pass
                actual_url = popup.url
                log(f"✓ 消息页新窗口已打开（{tag}）: {actual_url}")
                return await _fix_fingerprint_and_return(popup, actual_url, "popup")
            # 检查同窗口跳转
            current_url = page.url or ""
            if "/im" in current_url and current_url != old_url:
                log(f"✓ 消息页同窗口打开（{tag}）: {current_url}")
                return await _fix_fingerprint_and_return(page, current_url, "同窗口")
        return None

    # 尝试真人鼠标点击「消息」入口
    max_click_attempts = 3
    for attempt in range(1, max_click_attempts + 1):
        try:
            msg_bbox = await _find_msg_entry_bbox()
            if not msg_bbox:
                log(f"未找到消息入口元素（尝试 {attempt}/{max_click_attempts}）")
                await asyncio.sleep(0.8 + random.random() * 1.2)
                continue

            click_x = msg_bbox["x"] + random.uniform(-3, 3)
            click_y = msg_bbox["y"] + random.uniform(-2, 2)
            log(f"找到消息入口「{msg_bbox.get('text','')}」位置=({click_x:.0f},{click_y:.0f})，真人鼠标点击（尝试 {attempt}/{max_click_attempts}）")

            # 点击前先 hover（移动到目标 + 停顿，触发 mouseover 事件）
            # 某些导航组件需要 mouseover 激活后才响应 click
            await page.mouse.move(click_x, click_y)
            await asyncio.sleep(0.3 + random.random() * 0.5)

            old_url = page.url or ""

            # 真人鼠标点击：贝塞尔移动 + down + up
            await human_mouse_click(page, click_x, click_y)

            # 轮询等待 URL 变化或 popup（不用 expect_popup，避免同窗口 SPA 跳转误判）
            result = await _wait_for_im_navigation(old_url, 12.0, "真人点击")
            if result:
                return result

            # 真人鼠标点击未跳转，尝试用 locator.click() 备选（确保点击到正确元素）
            log(f"真人鼠标点击未跳转（尝试 {attempt}），改用 locator.click() 备选")
            try:
                old_url2 = page.url or ""
                # 用 Playwright locator 直接点击元素（它会自动滚动到元素并点击中心）
                loc = page.locator(':has-text("消息")').first
                if await loc.count() > 0:
                    await loc.click(timeout=5000)
                    result2 = await _wait_for_im_navigation(old_url2, 10.0, "locator点击")
                    if result2:
                        return result2
            except Exception as e:
                log(f"locator.click() 备选失败: {e}")

            log(f"点击尝试 {attempt}/{max_click_attempts} 失败，重试")
            await asyncio.sleep(0.5 + random.random() * 1.0)
        except Exception as e:
            log(f"真人点击消息失败（尝试 {attempt}）: {e}")
            await asyncio.sleep(0.5 + random.random() * 1.0)

    # 所有点击尝试都失败，回退：直接访问 target_url
    log("⚠ 真人鼠标点击消息入口失败，回退直接访问目标页（风控风险较高）")
    fallback_url = target_url or DEFAULT_TARGET_URL
    try:
        await page.goto(fallback_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log(f"目标页加载警告: {e}")
    await asyncio.sleep(2.0 + random.random() * 1.5)
    return page, fallback_url


async def solve_in_context(ctx, target_url: str, max_retries: int) -> dict:
    """在已注入 Cookie 的 context 中求解。失败后刷新重置 Baxia。"""
    result: dict[str, Any] = {
        "ok": False,
        "solved": False,
        "captchaDetected": False,
        "attempts": 0,
    }
    pages = ctx.pages
    page = pages[0] if pages else await ctx.new_page()
    # 截图目录优先使用 /tmp（容器 read-only 文件系统兼容）
    # fallback 到 cwd/screenshots（本地开发环境）
    _candidate_dirs = [
        os.environ.get("SLIDER_SCREENSHOT_DIR"),
        "/tmp/slider-screenshots",
        os.path.join(os.getcwd(), "screenshots"),
    ]
    screenshot_dir = next((d for d in _candidate_dirs if d), "/tmp/slider-screenshots")
    try:
        os.makedirs(screenshot_dir, exist_ok=True)
    except OSError:
        # cwd/screenshots 可能只读，回退到 /tmp
        screenshot_dir = "/tmp/slider-screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)

    # 监听 Baxia 校验响应，辅助判定成功（不依赖 DOM）
    net_success = {"flag": False}

    # 2026-08-02 重大修复：在 HTTP 响应拦截器中捕获 x5sec（不依赖浏览器上下文）
    # 问题：_collect_cookies_and_x5sec 依赖 ctx.cookies()/page.evaluate()，
    #       但 Baxia 验证后浏览器经常崩溃，导致 x5sec 永远无法提取。
    # 解决：在 _on_response 回调中直接从 Set-Cookie 头和 JSON 响应体提取 x5sec，
    #       这在浏览器崩溃之前就已完成（HTTP 响应到达即触发）。
    captured_x5sec = {"value": "", "source": ""}

    # 2026-08-01 新增：Baxia 验证 API 请求/响应分析器（增强版）
    # 目标：记录 Baxia 验证请求的参数（bx-pp/bx-ua/slidedata/x5secdata）和响应体，
    #       分析 x5sec 获取流程，为"伪造 x5sec 或绕过风控"方案提供数据支持。
    # 关键发现（线上日志分析）：
    #   - x5sec 可通过直接调用 Baxia 验证 API 获取，不需要真拖滑块
    #   - 请求需包含：bx-pp（WASM加密）、bx-ua（231!开头）、slidedata、x5secdata（SECDATA）、ppt、ts、v
    #   - bx-et 可默认为 "nosgn"
    #   - 线上日志显示只捕获了 JS 文件 GET 请求，未捕获验证 API POST 请求
    #   - 原因：验证 API URL 可能不含 Baxia 关键字，需要记录所有 POST 请求
    #   - "响应中包含 x5sec" 之前是误报（JS 源码中包含 x5sec 字符串），需过滤 JS 响应
    _baxia_api_keywords = ("baxia", "nocaptcha", "control", "_____tmd_____", "x5sec", "captcha", "slidedata")
    _baxia_api_domains = ("h5api.m.goofish.com", "h5api.m.taobao.com", "acs.m.taobao.com")
    # 过滤埋点/统计域名（这些不是 Baxia 验证请求，记录它们只会产生噪音）
    _noise_domains = ("gm.mmstat.com", "ynuf.aliapp.org", "retcode.taobao.com", "arms-retcode.aliyuncs.com")

    def _on_request(req) -> None:
        """记录所有 POST 请求和 Baxia 相关请求的参数（只读，不修改请求）。"""
        try:
            u = req.url or ""
            method = (req.method or "GET").upper()
            ul = u.lower()
            # 过滤埋点/统计请求（mmstat.com 等，不是 Baxia 验证请求）
            if any(d in ul for d in _noise_domains):
                return
            # 判断是否需要记录：
            # 1. 所有 POST 请求（验证 API 是 POST）
            # 2. URL 含 Baxia 关键字
            # 3. 请求到 goofish/taobao API 域名
            is_post = method == "POST"
            has_keyword = any(k in ul for k in _baxia_api_keywords)
            is_api_domain = any(d in ul for d in _baxia_api_domains)
            if not (is_post or has_keyword or is_api_domain):
                return
            # 过滤静态资源（JS/CSS/图片/字体）
            if any(u.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".gif", ".svg", ".woff", ".woff2")):
                if not is_post:
                    return
            log(f"🔍 [Baxia请求] {method} {u[:200]}")
            # 记录请求头中的加密参数（所有请求都检查，因为验证 API 可能用任意 URL）
            try:
                headers = req.headers
                bx_pp = headers.get("bx-pp") or headers.get("bx_pp")
                bx_ua = headers.get("bx-ua") or headers.get("bx_ua")
                bx_et = headers.get("bx-et") or headers.get("bx_et")
                if bx_pp:
                    log(f"🔍 [Baxia请求] ✓ bx-pp 长度={len(bx_pp)} 前100字符={bx_pp[:100]}")
                if bx_ua:
                    log(f"🔍 [Baxia请求] ✓ bx-ua 长度={len(bx_ua)} 前100字符={bx_ua[:100]}")
                if bx_et:
                    log(f"🔍 [Baxia请求] bx-et={bx_et[:50]}")
            except Exception:
                pass
            # 记录请求体（POST 请求可能包含 slidedata/x5secdata）
            try:
                body = req.post_data
                if body:
                    log(f"🔍 [Baxia请求] body 长度={len(body)} 前800字符={body[:800]}")
            except Exception:
                pass
        except Exception:
            pass

    async def _log_baxia_response(resp) -> None:
        """异步读取并记录 Baxia 验证响应体。"""
        try:
            u = resp.url or ""
            status = resp.status
            log(f"🔍 [Baxia响应] status={status} {u[:200]}")
            try:
                body = await resp.text()
                if body:
                    # 过滤 JS 响应（baxiaCommon.js 等 JS 源码中包含 "x5sec" 字符串，会误报）
                    content_type = resp.headers.get("content-type", "")
                    is_js = "javascript" in content_type or u.endswith(".js")
                    log(f"🔍 [Baxia响应] body 长度={len(body)} content-type={content_type[:50]} 前800字符={body[:800]}")
                    # 只在非 JS 响应中检测 x5sec（真正的 x5sec cookie 在 JSON 响应中）
                    if not is_js and "x5sec" in body:
                        log(f"🔍 [Baxia响应] ✓✓✓ 非JS响应中包含 x5sec！这是真正的验证结果！")
                        # 尝试提取 x5sec 值
                        try:
                            data = json.loads(body)
                            if isinstance(data, dict):
                                for k, v in data.items():
                                    val_str = str(v) if v is not None else ""
                                    if "x5sec" in str(k).lower() or "x5sec" in val_str.lower()[:200]:
                                        log(f"🔍 [Baxia响应] x5sec 字段: {k}={val_str[:200]}")
                                        x5sec_candidate = ""
                                        if isinstance(v, str) and v.startswith("x5sec="):
                                            x5sec_candidate = v.split("=", 1)[1].split(";")[0]
                                        elif isinstance(v, str) and "x5sec=" in v:
                                            m = re.search(r"x5sec=([^;]+)", v)
                                            if m:
                                                x5sec_candidate = m.group(1)
                                        elif k.lower() == "x5sec" and isinstance(v, str) and len(v) > 10:
                                            x5sec_candidate = v
                                        if x5sec_candidate and not captured_x5sec["value"]:
                                            captured_x5sec["value"] = x5sec_candidate
                                            captured_x5sec["source"] = f"response_body_{k}"
                                            log(f"🔑 [x5sec] 从响应体提取成功! source={k} value长度={len(x5sec_candidate)}")
                        except Exception as e:
                            log(f"🔍 [Baxia响应] JSON 解析失败: {e}")
                        if not captured_x5sec["value"]:
                            m = re.search(r'"x5sec"\s*[:=]\s*"([^"]{10,})"', body)
                            if m:
                                captured_x5sec["value"] = m.group(1)
                                captured_x5sec["source"] = "response_body_regex"
                                log(f"🔑 [x5sec] 从响应体正则提取成功! value长度={len(m.group(1))}")
            except Exception as e:
                log(f"🔍 [Baxia响应] 读取 body 失败: {e}")
        except Exception:
            pass

    def _on_response(resp) -> None:
        try:
            u = resp.url or ""
            ul = u.lower()
            method = ""
            try:
                method = (resp.request.method or "").upper()
            except Exception:
                pass
            # 2026-08-02 重大修复：从 Set-Cookie 响应头中提取 x5sec
            # 这是浏览器崩溃前就能捕获的，不依赖 ctx.cookies()/page.evaluate()
            if not captured_x5sec["value"]:
                try:
                    set_cookie = resp.headers.get("set-cookie", "")
                    if set_cookie and "x5sec=" in set_cookie:
                        m = re.search(r"x5sec=([^;]+)", set_cookie)
                        if m and m.group(1):
                            captured_x5sec["value"] = m.group(1)
                            captured_x5sec["source"] = f"set_cookie_header_{u[:80]}"
                            log(f"🔑 [x5sec] 从 Set-Cookie 头提取成功! url={u[:100]} value长度={len(m.group(1))}")
                except Exception:
                    pass
            # 记录所有 POST 响应 + Baxia 关键字响应 + API 域名响应
            is_post = method == "POST"
            has_keyword = any(k in ul for k in _baxia_api_keywords)
            is_api_domain = any(d in ul for d in _baxia_api_domains)
            if is_post or has_keyword or is_api_domain:
                # 异步记录响应体
                try:
                    asyncio.create_task(_log_baxia_response(resp))
                except Exception:
                    pass
            # 2xx 且非 punish 页面可能表示通过
            if has_keyword and resp.status == 200 and "punish" not in u and "deny" not in ul:
                pass
            # 消息 token 成功也算环境恢复信号
            if "idlemessage" in u and "token" in u and resp.status == 200 and "punish" not in u:
                net_success["flag"] = True
        except Exception:
            pass

    try:
        page.on("request", _on_request)
        page.on("response", _on_response)
    except Exception:
        pass

    # 根据目标 URL 类型选择导航策略：
    # - punish URL（搜索上下文）：直接 goto punish URL，触发搜索场景的滑块
    # - 其他 URL（消息页上下文）：拟人路径进入 /im，避免直接 /im 触发反爬
    # _navigate_to_target 返回 (page, actual_url)，actual_url 供后续 navigate_fresh 刷新复用
    page, actual_im_url = await _navigate_to_target(page, target_url or DEFAULT_TARGET_URL)
    # 2026-08-01：导航后重新挂载监听器（_navigate_to_target 可能产生新 page 对象）
    try:
        page.on("request", _on_request)
        page.on("response", _on_response)
    except Exception:
        pass
    log(f"当前操作页 URL: {page.url}")
    log(f"✓ 记录目标页 URL（后续刷新复用）: {actual_im_url}")

    if await page_shows_load_failure(page):
        log("⚠ 进入消息页即出现「加载失败」——浏览器环境很可能已被风控标记")
        shot = os.path.join(screenshot_dir, f"load-fail-entry-{int(time.time())}.png")
        try:
            await asyncio.wait_for(page.screenshot(path=shot, full_page=False), timeout=3.0)
            result["screenshotPath"] = shot
        except Exception:
            pass
        # 仍继续尝试：有时滑块后刷新可恢复

    url_l = (page.url or "").lower()
    if any(x in url_l for x in ("login.taobao.com", "login.goofish.com", "/login", "/uilogin")):
        result["error"] = "Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie"
        result["isLoginPage"] = True
        return result

    human_action_count = 0
    HUMAN_ACTION_THRESHOLD = 3
    # 2026-08-01 修复：禁用软重置（MAX_HUMAN_ACTIONS=0）
    # 原因：软重置流程（关闭弹窗→打开首页→重新点击消息入口→等待新窗口）消耗 20-30 秒，
    # 在 120s 超时预算内只能完成 1 轮拖动，第 2 轮刚开始就超时。
    # 禁用后 3 次拖动失败立即返回，让上层冷却机制处理，避免无效时间消耗。
    MAX_HUMAN_ACTIONS = 0
    last_error = ""
    last_screenshot = None
    load_fail_streak = 0

    for attempt in range(1, max_retries + 1):
        result["attempts"] = attempt
        log("=" * 50)
        log(f"第 {attempt}/{max_retries} 次尝试")
        await diagnose_frames(page)

        # 风险探针：记录关键环境信号（用于分析为何人工也失败）
        try:
            probe = await page.evaluate(
                """() => ({
                  webdriver: navigator.webdriver,
                  languages: navigator.languages,
                  plugins: navigator.plugins ? navigator.plugins.length : -1,
                  chrome: !!window.chrome,
                  hw: navigator.hardwareConcurrency,
                  ua: navigator.userAgent.slice(0, 80),
                  hasCdc: Object.keys(window).some(k => k.startsWith('cdc_') || k.startsWith('$cdc_')),
                })"""
            )
            log(f"环境探针: {probe}")
        except Exception:
            pass

        if await page_shows_load_failure(page):
            load_fail_streak += 1
            last_error = "页面显示加载失败（环境/会话被风控）"
            log(f"⚠ {last_error} streak={load_fail_streak}")
            shot = os.path.join(screenshot_dir, f"load-fail-{attempt}-{int(time.time())}.png")
            try:
                await asyncio.wait_for(page.screenshot(path=shot, full_page=False), timeout=3.0)
                last_screenshot = shot
                result["screenshotPath"] = shot
            except Exception:
                pass
            # 2026-08-03 强化：加载失败不立即返回，改为刷新重试
            # 原因：用户反馈"10秒就失败"的根因之一就是加载失败立即返回，
            #       导致没有机会检查 punish iframe 和拖动滑块。
            #       Baxia 的"加载失败"可能是暂时的，刷新后可能恢复。
            #       连续 3 次加载失败才放弃，给 Baxia 风控恢复机会。
            if load_fail_streak >= 3:
                result["error"] = (
                    f"页面连续 {load_fail_streak} 次显示加载失败（Baxia 风控惩罚）："
                    "自动化浏览器环境被闲鱼风控标记，请等待冷却期后重试或更换 Cookie"
                )
                return result
            # 加载失败时尝试硬重置（navigate_fresh），给 Baxia 重新评估会话的机会
            log(f"加载失败 streak={load_fail_streak}，尝试硬重置刷新页面...")
            page, actual_im_url = await navigate_fresh(page, actual_im_url, hard=True)
            # 等待页面重新加载
            await asyncio.sleep(2.0 + random.random() * 1.5)
            continue
        else:
            load_fail_streak = 0

        url_l = (page.url or "").lower()
        if any(x in url_l for x in ("login.taobao.com", "login.goofish.com", "/login", "/uilogin")):
            result["error"] = "Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie"
            return result

        detected, detected_selector = await detect_captcha_container(page)
        has_punish = any(
            "punish" in ((f.url or "").lower()) or "_____tmd_____" in ((f.url or "").lower())
            for f in page.frames
        )
        log(f"滑块容器检测: detected={detected}, selector={detected_selector}, has_punish_frame={has_punish}")

        # 2026-08-01 重大修正：punish 状态下仍尝试拖动滑块（脱离 punish 的唯一方法）
        # 原逻辑（已废弃）：检测到 punish 立即返回 → 账号永远无法脱离 punish → 0% 成功率
        # 2026-08-03 强化：punish 状态下允许 max_retries 次拖动（原 2 次）
        # 原因：多策略轮换需要更多尝试机会，不同策略可能突破 punish
        # 60 秒冷却规则由 captcha_backoff.py 保证，这里不重复限制
        # 详见 .trae/rules/cookie-valid-ws-persistence.md 第 9 条核心约束。
        if has_punish and attempt >= max_retries:
            result["error"] = (
                f"账号已被 Baxia 风控惩罚（punish 状态），第 {attempt} 次尝试跳过拖动避免加码。"
                f"前 {max_retries - 1} 次已尝试拖动未通过，请等待 60 秒冷却后重试"
            )
            log(f"⚠ {result['error']}")
            result["captured_x5sec"] = captured_x5sec.get("value", "")
            return result
        if has_punish:
            log(f"⚠ 检测到 punish 状态，仍尝试拖动滑块以脱离 punish（attempt={attempt}/{max_retries}）")

        if not detected and not has_punish:
            # 2026-08-03 修复"假成功"：页面加载失败（chrome-error/ERR_TIMED_OUT）时
            # document.body 为空导致 page_shows_load_failure 检测不到（evaluate 抛异常），
            # 且 detect_captcha_container 返回 False、check_solved 返回 True，
            # 此前会误判为"验证通过"并返回无 x5sec 的 cookies → 后续 WS 重连必然失败。
            # 修复：URL 为错误页时不得判定通过，硬重置刷新后重试。
            url_l2 = (page.url or "").lower()
            if "chrome-error://" in url_l2 or "chromewebdata" in url_l2:
                log(f"⚠ 页面为浏览器错误页（{url_l2}），不能判定验证通过，硬重置刷新重试")
                page, actual_im_url = await navigate_fresh(page, actual_im_url, hard=True)
                await asyncio.sleep(2.0 + random.random() * 1.5)
                continue
            if await check_solved(page):
                log("✓ 未检测到滑块，验证通过！")
                result.update({"ok": True, "solved": True, "captchaDetected": False})
                await _collect_cookies_and_x5sec(ctx, page, result, captured_x5sec.get("value", ""))
                return result
            # 可能还在加载
            await asyncio.sleep(2.0)
            detected, detected_selector = await detect_captcha_container(page)

        log("等待滑块按钮加载...")
        slider_info = await wait_for_slider_ready(page, max_wait_ms=10000)
        if slider_info and slider_info.get("is_login_page"):
            result["error"] = "Cookie Session 已过期，页面被重定向到登录页，请重新扫码登录闲鱼账号获取新 Cookie"
            return result
        if slider_info and slider_info.get("already_solved"):
            log("✓ 用户已手动完成滑块验证 / 无需验证")
            result.update({"ok": True, "solved": True, "captchaDetected": True})
            await _collect_cookies_and_x5sec(ctx, page, result, captured_x5sec.get("value", ""))
            return result

        if not slider_info:
            last_error = "未找到滑块按钮"
            log(last_error)
            shot = os.path.join(screenshot_dir, f"slider-not-found-{int(time.time())}.png")
            try:
                await asyncio.wait_for(page.screenshot(path=shot, full_page=False), timeout=3.0)
                last_screenshot = shot
                result["screenshotPath"] = shot
            except Exception:
                pass
            log("刷新页面重试（彻底重置）...")
            page, actual_im_url = await navigate_fresh(page, actual_im_url)
            continue

        result["captchaDetected"] = True
        button_el = slider_info.get("button")
        sx, sy, dist = slider_info["x"], slider_info["y"], float(slider_info["distance"])
        # 不再默认大幅过冲；终点微调交给各拖拽策略
        log(f"找到滑块: x={sx:.1f}, y={sy:.1f}, distance={dist:.1f}")

        # 拖动前再次确认是否已通过
        if await check_solved(page):
            detected2, _ = await detect_captcha_container(page)
            if not detected2:
                result.update({"ok": True, "solved": True, "captchaDetected": True})
                await _collect_cookies_and_x5sec(ctx, page, result, captured_x5sec.get("value", ""))
                return result

        pre_path = os.path.join(screenshot_dir, f"slider-pre-{attempt}-{int(time.time())}.png")
        try:
            await asyncio.wait_for(page.screenshot(path=pre_path, full_page=False), timeout=3.0)
            last_screenshot = pre_path
        except Exception:
            pass

        # 拖动前：先“看”弹窗 0.8~2s，模拟真人阅读
        await asyncio.sleep(0.8 + random.random() * 1.2)
        for _ in range(2 + random.randint(0, 2)):
            await page.mouse.move(
                sx + random.uniform(-40, 20),
                sy + random.uniform(-25, 25),
                steps=random.randint(4, 10),
            )
            await asyncio.sleep(0.06 + random.random() * 0.15)

        try:
            # 2026-08-03 强化：多策略拖动组合，每次 attempt 用不同策略
            # 原因：单一策略（xdotool）失败后 Baxia 可能已适应，换策略可能突破
            # 策略轮换顺序：
            #   attempt 1: xdotool（X11 系统级鼠标，绕过 CDP，最强）
            #   attempt 2: human_physics_drag（CDP + Minimum-Jerk 轨迹）
            #   attempt 3: bezier_mouse_drag（三次贝塞尔曲线，慢-快-慢节奏）
            #   attempt 4: microstep_drag（小步匀加速，贴近部分真人习惯）
            #   attempt 5: xdotool（再试一次，可能 Baxia 状态已恢复）
            slider_frame = slider_info.get("frame")
            strategy_index = (attempt - 1) % 5
            strategy_names = ["xdotool", "human_physics", "bezier", "microstep", "xdotool"]
            strategy_name = strategy_names[strategy_index]
            log(f"  attempt={attempt} 【{strategy_name}】策略（多策略轮换）")

            if strategy_name == "xdotool":
                # xdotool_drag 内部会检测 xdotool 是否可用，不可用时回退到 human_physics_drag
                # 超时 30 秒（xdotool 每步有 subprocess 开销，比 CDP 慢）
                await asyncio.wait_for(xdotool_drag(page, sx, sy, dist, attempt), timeout=30.0)
            elif strategy_name == "human_physics":
                # CDP + Minimum-Jerk 轨迹（x(t) = 10t^3 - 15t^4 + 6t^5）
                await asyncio.wait_for(human_physics_drag(page, sx, sy, dist, attempt), timeout=20.0)
            elif strategy_name == "bezier":
                # 三次贝塞尔曲线，慢-快-慢节奏，X 近似单调递增
                await asyncio.wait_for(bezier_mouse_drag(page, sx, sy, dist, attempt), timeout=20.0)
            elif strategy_name == "microstep":
                # 小步匀加速，每步 2~4px，总时长约 1.2~2.2s
                await asyncio.wait_for(microstep_drag(page, sx, sy, dist, attempt), timeout=20.0)
        except asyncio.TimeoutError:
            last_error = f"拖动超时（10s），page.mouse 可能卡住"
            log(f"× {last_error}")
            # 超时后不 navigate_fresh（太慢），直接点重试按钮
            clicked = await click_retry_if_needed(page)
            if clicked:
                log("超时后已点击重试，等待新滑块...")
                await asyncio.sleep(1.5 + random.random() * 1.0)
            continue
        except Exception as e:
            last_error = f"拖动异常: {type(e).__name__}: {e}"
            log(last_error)
            # 异常后不 navigate_fresh（太慢），直接点重试按钮
            clicked = await click_retry_if_needed(page)
            if clicked:
                log("异常后已点击重试，等待新滑块...")
                await asyncio.sleep(1.5 + random.random() * 1.0)
            continue

        # 2026-08-01 优化：增加等待时间到 4-7 秒
        # 原因：Baxia 异步处理滑块验证结果，2.6-4.4 秒可能不够，
        #       导致 check_solved 在滑块通过前检测，误判为未通过。
        #       增加到 4-7 秒给 Baxia 足够时间处理并更新 DOM。
        result_wait = 4.0 + random.random() * 3.0
        log(f"等待 {result_wait:.1f} 秒验证结果...")
        await asyncio.sleep(result_wait)

        post_path = os.path.join(screenshot_dir, f"slider-post-{attempt}-{int(time.time())}.png")
        try:
            await asyncio.wait_for(page.screenshot(path=post_path, full_page=False), timeout=5.0)
            last_screenshot = post_path
            result["screenshotPath"] = post_path
        except Exception:
            pass

        # check_solved 加超时保护（5 秒），防止卡住
        try:
            solved = await asyncio.wait_for(check_solved(page), timeout=8.0)
        except asyncio.TimeoutError:
            log("⚠ check_solved 超时（5s），视为未通过")
            solved = False
        except Exception:
            solved = False
        # 网络弱信号：token 接口 200 且无 punish
        if not solved and net_success.get("flag"):
            await asyncio.sleep(1.0)
            try:
                still = await asyncio.wait_for(detect_captcha_container(page), timeout=5.0)
            except asyncio.TimeoutError:
                still = (True, None)
            if not still[0]:
                log("✓ 网络信号显示会话恢复且弹窗消失，视为通过")
                solved = True
            net_success["flag"] = False

        if solved:
            # 检查是否“下载消息失败”假阳性
            try:
                body = await page.evaluate(
                    "() => document.body ? document.body.innerText.substring(0, 400) : ''"
                )
                if body and ("下载消息失败" in body or "加载失败" in body):
                    log("滑块通过但页面显示加载失败/下载消息失败，刷新重试")
                    page, actual_im_url = await navigate_fresh(page, actual_im_url, hard=False)
                    continue
            except Exception:
                pass
            log("✓✓✓ 滑块验证通过！")
            result.update({"ok": True, "solved": True, "captchaDetected": True})
            await _collect_cookies_and_x5sec(ctx, page, result, captured_x5sec.get("value", ""))
            return result

        last_error = f"第 {attempt} 次拖动未通过"
        log(f"× {last_error}")

        # 2026-08-03 强化：允许 max_retries 次尝试，每次用不同策略
        # 原逻辑（已废弃）：attempt >= 2 放弃重试 → 只拖动 1 次就放弃
        # 新逻辑：attempt >= max_retries 才放弃，配合多策略轮换
        # 原因：用户明确要求"应当仍可以通过模拟轨迹的方式通过滑块"，
        #       不同策略可能突破 Baxia 的轨迹检测，多策略组合提高成功率。
        #       60 秒冷却规则由 captcha_backoff.py 保证，这里不重复限制。
        if attempt >= max_retries:
            result["error"] = (
                f"连续 {attempt} 次拖动未通过（已用 {max_retries} 种策略），"
                "请等待冷却期后重试"
            )
            log(f"⚠ {result['error']}")
            return result

        # 优先点「框体重试」并等待新滑块，而不是立刻清会话硬刷新
        clicked = await click_retry_if_needed(page)
        if clicked:
            log("已点击框体重试，等待新滑块就绪...")
            await asyncio.sleep(2.0 + random.random() * 1.5)
            new_info = await wait_for_slider_ready(page, max_wait_ms=8000)
            if new_info and not new_info.get("is_login_page") and not new_info.get("already_solved"):
                log("新滑块已就绪，下一轮直接拖")
                await asyncio.sleep(0.5 + random.random() * 0.8)
                continue

        # 连续失败：关弹窗 + 软重置（不清 storage）
        if attempt >= HUMAN_ACTION_THRESHOLD and human_action_count < MAX_HUMAN_ACTIONS:
            human_action_count += 1
            log(
                f"=== 连续 {attempt} 次失败，触发软重置 "
                f"({human_action_count}/{MAX_HUMAN_ACTIONS}) ==="
            )
            closed = await close_captcha_dialog(page)
            if closed:
                log("已关闭弹窗，等待页面变化...")
                await asyncio.sleep(1.5)
            page, actual_im_url = await navigate_fresh(page, actual_im_url, hard=False)
            cooldown = 4.0 + random.random() * 4.0
            log(f"冷静期 {cooldown:.1f}s ...")
            await asyncio.sleep(cooldown)
        else:
            # 轻量等待后再试同页新滑块，降低连续 punish 刷新
            await asyncio.sleep(1.2 + random.random() * 1.5)

    # 全自动：不再等待人工拖拽，直接失败返回
    log("=== 全自动重试已用完，不再进入半自动人工等待 ===")
    result["error"] = last_error or f"滑块验证未通过，已全自动重试 {max_retries} 次"
    if last_screenshot:
        result["screenshotPath"] = last_screenshot
    result["captured_x5sec"] = captured_x5sec.get("value", "")
    return result


async def export_cookies(ctx) -> str:
    try:
        cookies = await ctx.cookies()
        # 优先 goofish / taobao 相关
        parts = []
        for c in cookies:
            name = c.get("name") or ""
            value = c.get("value") or ""
            if name and value is not None:
                parts.append(f"{name}={value}")
        return "; ".join(parts)
    except Exception as e:
        log(f"导出 cookies 失败: {e}")
        return ""


async def extract_x5sec(ctx) -> str:
    """从浏览器 context 中提取 x5sec cookie 值。

    x5sec 是 Baxia 滑块验证成功后设置的 cookie，
    后续 goofish API 请求带上这个 cookie 就不会触发滑块验证。
    提取后可缓存到数据库，实现"一次求解，长期免滑块"。
    """
    try:
        cookies = await ctx.cookies()
        for c in cookies:
            name = c.get("name") or ""
            if name == "x5sec":
                value = c.get("value") or ""
                domain = c.get("domain") or ""
                expires = c.get("expires") or -1
                log(f"🔑 [x5sec] 提取成功! domain={domain} value长度={len(value)} expires={expires}")
                return value
        log("🔑 [x5sec] cookie 中未找到 x5sec（可能未触发滑块或验证未通过）")
        return ""
    except Exception as e:
        log(f"🔑 [x5sec] 提取失败: {e}")
        return ""


async def _collect_cookies_and_x5sec(ctx, page, result: dict, captured_x5sec_val: str = "") -> None:
    """在 ctx 还活着时收集 cookies 和 x5sec，避免 ctx 关闭后无法提取。

    问题背景：solve_in_context 返回 solved=True 后，_launch_solve_once 再调用
    export_cookies(ctx) / extract_x5sec(ctx) 时，ctx 可能已被浏览器崩溃关闭，
    抛出 "BrowserContext.cookies: Target page, context or browser has been closed"，
    导致 x5sec 丢失、无法缓存到 Redis，WS 重连时无法免滑块恢复。

    解决方案：在 solve_in_context 内部 solved=True 时立即调用此函数，
    将 cookies 和 x5sec 写入 result，_launch_solve_once 直接复用。
    增加 page.evaluate("document.cookie") 作为 fallback（不依赖 ctx 状态）。
    """
    # 方案 A：通过 ctx.cookies() 提取（优先，能拿到 HttpOnly cookie 如 x5sec）
    try:
        cookies = await ctx.cookies()
        if cookies:
            parts = []
            x5sec_val = ""
            for c in cookies:
                name = c.get("name") or ""
                value = c.get("value") or ""
                if name and value is not None:
                    parts.append(f"{name}={value}")
                if name == "x5sec" and value:
                    x5sec_val = value
            if parts:
                result["cookies"] = "; ".join(parts)
                result["cookieCount"] = len(parts)
            if x5sec_val:
                result["x5sec"] = x5sec_val
                log(f"🔑 [x5sec] solve_in_context 内 ctx.cookies 提取成功! value长度={len(x5sec_val)}")
                return
    except Exception as e:
        log(f"收集 cookies/x5sec: ctx.cookies 失败（ctx 可能已关闭）: {e}")

    # 方案 B：通过 page.evaluate("document.cookie") 提取（fallback，不依赖 ctx）
    # 注意：document.cookie 无法读取 HttpOnly cookie，但 x5sec 通常不是 HttpOnly
    try:
        doc_cookie = await page.evaluate("() => document.cookie")
        if doc_cookie:
            result["cookies"] = doc_cookie
            result["cookieCount"] = doc_cookie.count("=")
            # 从 document.cookie 中提取 x5sec
            m = re.search(r"(?:^|;\s*)x5sec=([^;]+)", doc_cookie)
            if m and m.group(1):
                result["x5sec"] = m.group(1)
                log(f"🔑 [x5sec] solve_in_context 内 document.cookie 提取成功! value长度={len(m.group(1))}")
                return
    except Exception as e:
        log(f"收集 cookies/x5sec: page.evaluate 失败（page 可能已关闭）: {e}")

    # 方案 C（2026-08-02 新增）：使用 HTTP 响应拦截器捕获的 x5sec
    # 这是从 Set-Cookie 头或 JSON 响应体中提取的，在浏览器崩溃之前就已完成
    if captured_x5sec_val and not result.get("x5sec"):
        result["x5sec"] = captured_x5sec_val
        result["x5secSource"] = "http_response_interceptor"
        log(f"🔑 [x5sec] 从 HTTP 响应拦截器提取成功! value长度={len(captured_x5sec_val)}")


# ============================================================
# 指纹诊断探针：实时记录关键检测信号，便于对比优化效果
# ============================================================
# 作用：每次求解前打印当前浏览器环境的机器人特征信号，定位被 Baxia 识破的根因。
# 告警维度覆盖 Baxia 2026 实测的 14+ 检测点。
_FINGERPRINT_PROBE_JS = r"""
(() => {
  const signals = {};
  try { signals.webdriver = navigator.webdriver; } catch (e) { signals.webdriver = 'ERR'; }
  try { signals.pluginsLength = (navigator.plugins && navigator.plugins.length) || 0; } catch (e) { signals.pluginsLength = 'ERR'; }
  try { signals.userAgentData = !!(navigator.userAgentData); } catch (e) { signals.userAgentData = 'ERR'; }
  try { signals.connection = !!(navigator.connection); } catch (e) { signals.connection = 'ERR'; }
  try { signals.getBattery = typeof navigator.getBattery === 'function'; } catch (e) { signals.getBattery = 'ERR'; }
  try { signals.chrome = !!(window.chrome && window.chrome.runtime); } catch (e) { signals.chrome = 'ERR'; }
  try { signals.outerWidth = window.outerWidth; } catch (e) { signals.outerWidth = 'ERR'; }
  try { signals.innerWidth = window.innerWidth; } catch (e) { signals.innerWidth = 'ERR'; }
  try { signals.cdc_ = !!(document.querySelector('[id*="cdc_"]') || window.cdc_adoQpoasnfa76pfcZLmcfl_Array || window.cdc_adoQpoasnfa76pfcZLmcfl_Promise || window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol); } catch (e) { signals.cdc_ = 'ERR'; }
  try { signals.playwright = !!(window.__playwright__ || window.__pw_manual); } catch (e) { signals.playwright = 'ERR'; }
  try { signals.voices = (window.speechSynthesis && window.speechSynthesis.getVoices && window.speechSynthesis.getVoices().length) || 0; } catch (e) { signals.voices = 'ERR'; }
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
    if (gl) {
      const ext = gl.getExtension('WEBGL_debug_renderer_info');
      signals.webglVendor = ext ? gl.getParameter(ext.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR);
      signals.webglRenderer = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
    } else {
      signals.webglVendor = 'no-webgl';
      signals.webglRenderer = 'no-webgl';
    }
  } catch (e) { signals.webglVendor = 'ERR'; signals.webglRenderer = 'ERR'; }
  try { signals.permissions = typeof navigator.permissions !== 'undefined'; } catch (e) { signals.permissions = 'ERR'; }
  try { signals.languages = JSON.stringify(navigator.languages || []); } catch (e) { signals.languages = 'ERR'; }
  return signals;
})()
"""


async def _log_fingerprint_probe(page, label: str = "probe") -> dict:
    """实时记录 14+ 检测信号并告警。

    用法：在每次求解前调用，打印当前浏览器环境的机器人特征信号。
    出现告警信号时打印 ⚠ 告警；全部通过时打印 ✓ 通过。
    """
    try:
        signals = await page.evaluate(_FINGERPRINT_PROBE_JS)
    except Exception as e:
        log(f"⚠ 指纹探针[{label}] 执行失败: {e}")
        return {}

    if not isinstance(signals, dict):
        log(f"⚠ 指纹探针[{label}] 返回非 dict: {signals}")
        return {}

    alerts: list[str] = []

    # 1. webdriver 必须为 undefined / false
    if signals.get("webdriver") not in (None, False, "undefined"):
        alerts.append(f"webdriver={signals.get('webdriver')}")

    # 2. plugins.length 必须大于 0
    try:
        if int(signals.get("pluginsLength", 0)) <= 0:
            alerts.append("plugins.length=0（headless 信号）")
    except (TypeError, ValueError):
        alerts.append(f"plugins.length={signals.get('pluginsLength')}")

    # 3. userAgentData 必须存在（Chrome 131+）
    if signals.get("userAgentData") is not True:
        alerts.append("userAgentData 缺失（Client Hints）")

    # 4. connection 必须存在
    if signals.get("connection") is not True:
        alerts.append("connection 缺失（Network Information API）")

    # 5. getBattery 必须为 function
    if signals.get("getBattery") is not True:
        alerts.append("getBattery 缺失")

    # 6. window.chrome.runtime 必须存在
    if signals.get("chrome") is not True:
        alerts.append("window.chrome.runtime 缺失")

    # 7. outerWidth 必须 > innerWidth（headless 下相等）
    try:
        ow = int(signals.get("outerWidth", 0))
        iw = int(signals.get("innerWidth", 0))
        if ow <= iw:
            alerts.append(f"outerWidth({ow})<=innerWidth({iw})（headless 信号）")
    except (TypeError, ValueError):
        alerts.append(f"outerWidth={signals.get('outerWidth')} innerWidth={signals.get('innerWidth')}")

    # 8. cdc_ 痕迹必须不存在
    if signals.get("cdc_") is True:
        alerts.append("cdc_ CDP 注入痕迹存在")

    # 9. __playwright 必须不存在
    if signals.get("playwright") is True:
        alerts.append("__playwright 对象存在")

    # 10. speechSynthesis.getVoices().length 必须 > 0
    try:
        if int(signals.get("voices", 0)) <= 0:
            alerts.append("speechSynthesis.getVoices()=0（headless 信号）")
    except (TypeError, ValueError):
        alerts.append(f"voices={signals.get('voices')}")

    # 11. WebGL renderer 不能包含 SwiftShader
    renderer = str(signals.get("webglRenderer", ""))
    if "SwiftShader" in renderer or "swiftshader" in renderer:
        alerts.append(f"WebGL renderer={renderer}（SwiftShader 机器人强信号）")
    if renderer in ("no-webgl", "ERR", ""):
        alerts.append(f"WebGL renderer 异常: {renderer}")

    # 12. permissions API 必须存在
    if signals.get("permissions") is not True:
        alerts.append("navigator.permissions 缺失")

    # 13. languages 不能为空数组
    langs = str(signals.get("languages", "[]"))
    if langs in ("[]", "null", "ERR"):
        alerts.append(f"navigator.languages={langs}")

    if alerts:
        log(f"⚠ 指纹探针告警[{label}]: {' | '.join(alerts)}")
    else:
        log(f"✓ 指纹探针[{label}] 全部通过，无机器人信号")

    # 完整信号也打印一遍（debug 用）
    log(f"  指纹详情[{label}]: {json.dumps(signals, ensure_ascii=False)}")
    return signals


# ============================================================
# 半自动人工兜底：全自动失败后保留浏览器窗口供人工拖拽
# ============================================================
# 设计动机：用户反馈"通过自动化打开的窗口，人工拖拽也失败"。
# 根因是浏览器环境被标为机器人，而非拖拽轨迹问题。
# 但在持久化 profile + stealth 增强后，环境会接近真人浏览器，
# 此时人工拖拽的成功率会显著提升。
# 本函数在全自动失败后保留窗口，给人工最后一次机会。
async def _semi_auto_human_fallback(
    ctx,
    solve_result: dict,
    timeout_sec: int = 120,
) -> dict:
    """半自动人工兜底模式。

    全自动失败后保留浏览器窗口，提示人工拖拽滑块。
    每 2 秒检测一次 check_solved，通过则返回成功。
    超时则返回原 solve_result（保留失败信息）。
    """
    log("=== 进入半自动人工兜底模式 ===")
    log(f"请在浏览器窗口中手动完成滑块验证（{timeout_sec} 秒超时）")

    pages = ctx.pages if ctx else []
    if not pages:
        log("半自动兜底失败：无活动页面")
        return solve_result

    page = pages[0]
    deadline = time.time() + timeout_sec
    poll_interval = 2.0

    while time.time() < deadline:
        try:
            # 检测当前页面是否已通过验证
            solved = await check_solved(page)
            if solved:
                elapsed = int(timeout_sec - (deadline - time.time()))
                log(f"✓ 人工拖拽成功！耗时 {elapsed}s")
                solve_result.update({
                    "solved": True,
                    "ok": True,
                    "engine": "Playwright+Human",
                    "humanFallback": True,
                    "humanSolveDurationSec": elapsed,
                })
                # 导出最新 cookie
                try:
                    fresh = await export_cookies(ctx)
                    if fresh:
                        solve_result["cookies"] = fresh
                        solve_result["cookieCount"] = fresh.count("=")
                except Exception as e:
                    log(f"export_cookies 失败（半自动兜底）: {e}")
                # 提取 x5sec（仅在缺失时补充）
                if not solve_result.get("x5sec"):
                    try:
                        x5sec = await extract_x5sec(ctx)
                        if x5sec:
                            solve_result["x5sec"] = x5sec
                    except Exception:
                        pass
                # 兜底：从 cookies 字符串提取 x5sec
                if not solve_result.get("x5sec") and solve_result.get("cookies"):
                    m = re.search(r"(?:^|;\s*)x5sec=([^;]+)", solve_result["cookies"])
                    if m and m.group(1):
                        solve_result["x5sec"] = m.group(1)
                        log(f"🔑 [x5sec] 半自动兜底从 cookies 字符串提取成功! value长度={len(m.group(1))}")
                return solve_result
        except Exception as e:
            log(f"半自动检测异常（继续等待）: {e}")

        remaining = int(deadline - time.time())
        if remaining > 0 and remaining % 10 == 0:
            log(f"半自动兜底等待中... 剩余 {remaining}s")
        await asyncio.sleep(poll_interval)

    log("✗ 半自动人工兜底超时，未完成验证")
    solve_result["humanFallback"] = False
    solve_result["humanFallbackTimeout"] = True
    return solve_result


async def silent_extract_x5sec(
    playwright,
    chrome_path: str,
    ua: str,
    cookie_str: str,
    target_url: str = "https://www.goofish.com/im",
    proxy: Optional[dict] = None,
    profile_strategy: str = "temp",
    timeout_sec: int = 8,
) -> dict:
    """静默 x5sec 提取：不拖滑块，依赖浏览器 Baxia JS 静默验证获取 x5sec。

    2026-08-02 x5sec 主方案（方案 B）。
    详见 .trae/rules/x5sec-research-knowledge.md 第三章方案 B。

    流程：
    1. 启动浏览器（patchright + temp profile）
    2. 清除风控 cookie（x5sectag/x5sec/x5secdata/tfstk 等）
    3. 注入 cookie，导航到 /im
    4. HTTP 响应拦截器捕获 x5sec（Set-Cookie 头）
    5. 等待 timeout_sec 秒或事件驱动 x5sec 出现
    6. 返回 x5sec
    """
    start_time = time.time()
    result: dict[str, Any] = {
        "ok": False,
        "x5sec": "",
        "source": "",
        "error": "",
        "durationMs": 0,
    }

    try:
        ensure_temp_space()
    except Exception as e:
        log(f"[silent] 清理临时目录失败（继续尝试）: {e}")

    user_data_dir = _resolve_profile_dir(profile_strategy, cookie_str=cookie_str)
    prepare_profile_dir(user_data_dir)

    captured_x5sec = {"value": "", "source": ""}

    def _on_response(resp) -> None:
        try:
            u = resp.url or ""
            if not captured_x5sec["value"]:
                try:
                    set_cookie = resp.headers.get("set-cookie", "")
                    if set_cookie and "x5sec=" in set_cookie:
                        m = re.search(r"x5sec=([^;]+)", set_cookie)
                        if m and m.group(1):
                            captured_x5sec["value"] = m.group(1)
                            captured_x5sec["source"] = f"set_cookie_header_{u[:80]}"
                            log(f"🔑 [silent] 从 Set-Cookie 头提取成功! url={u[:100]} value长度={len(m.group(1))}")
                except Exception:
                    pass
        except Exception:
            pass

    ctx = None
    try:
        log(f"=== [silent] 启动静默提取（profile={profile_strategy} patchright={_USING_PATCHRIGHT} timeout={timeout_sec}s）===")

        if _USING_PATCHRIGHT:
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
                user_agent=ua,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                    "--window-position=0,0",
                    "--lang=zh-CN",
                ],
            )
        else:
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                user_agent=ua,
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_default_args=["--enable-automation"],
                args=_chrome_stealth_args(),
            )
        if proxy and proxy.get("server"):
            launch_kwargs["proxy"] = {
                "server": str(proxy["server"]),
                **({"username": str(proxy["username"])} if proxy.get("username") else {}),
                **({"password": str(proxy["password"])} if proxy.get("password") else {}),
            }
        try:
            ctx = await playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            log(f"[silent] launch_persistent_context 失败，重试精简参数: {e}")
            launch_kwargs.pop("timezone_id", None)
            launch_kwargs["args"] = [
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
            ]
            ctx = await playwright.chromium.launch_persistent_context(**launch_kwargs)

        if _USING_PATCHRIGHT:
            await ctx.add_init_script(_ADVANCED_FINGERPRINT_SCRIPT)
        else:
            await ctx.add_init_script(STEALTH_INIT_SCRIPT)

        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            page.on("response", _on_response)
        except Exception:
            pass

        try:
            await page.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log(f"[silent] 预热域导航警告: {e}")

        clean_cookie_str = strip_risk_cookies(cookie_str)
        cookies = parse_cookie_string(clean_cookie_str, ".goofish.com")
        cookies += parse_cookie_string(clean_cookie_str, "www.goofish.com")
        if cookies:
            try:
                await ctx.add_cookies(cookies)
                log(f"[silent] 注入 {len(cookies)} 条 cookies")
            except Exception as e:
                log(f"[silent] 注入 cookies 警告: {e}")

        try:
            await page.reload(wait_until="domcontentloaded", timeout=30000)
        except Exception:
            pass

        if _USING_PATCHRIGHT:
            try:
                await page.evaluate(_ADVANCED_FINGERPRINT_SCRIPT)
            except Exception as e:
                log(f"[silent] 指纹强制修复异常: {e}")

        log(f"[silent] 导航到 {target_url}，等待 Baxia JS 静默验证...")
        try:
            await page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            log(f"[silent] 目标页导航警告: {e}")

        current_url = page.url or ""
        log(f"[silent] 当前 URL: {current_url[:120]}")
        try:
            _title = await page.title()
            log(f"[silent] 页面标题: {_title}")
        except Exception:
            pass
        # 检查是否跳转到登录页（Cookie 真正失效）
        if "login.taobao.com" in current_url or "login.goofish.com" in current_url or "/uiLogin" in current_url:
            result["source"] = "login_redirect"
            result["error"] = f"Cookie 失效，跳转登录页: {current_url[:100]}"
            log(f"[silent] ⚠ Cookie 失效，跳转登录页: {current_url[:100]}")
            result["durationMs"] = int((time.time() - start_time) * 1000)
            return result

        # 2026-08-02 关键发现：/im 页面本身不触发 Baxia 验证，x5sec 只在调用 MTOP API 时才会被设置。
        # 主动调用 MTOP token API 触发 Baxia 静默验证。
        log(f"[silent] 主动调用 MTOP token API 触发 Baxia 静默验证...")
        try:
            mtop_result = await page.evaluate("""async () => {
                try {
                    const m_h5_tk_match = document.cookie.match(/_m_h5_tk=([^;]+)/);
                    const m_h5_tk = m_h5_tk_match ? m_h5_tk_match[1] : '';
                    if (!m_h5_tk) return { ok: false, error: 'no _m_h5_tk in cookie' };

                    const token_part = m_h5_tk.split('_')[0];
                    const ts = Date.now();
                    // 调用 WS token 刷新 API（与 ws_token.py 中的 _call_token_api 一致）
                    const api = 'mtop.taobao.idlemessage.pc.login.token';
                    const url = 'https://h5api.m.goofish.com/h5/' + api + '/1.0/?jsv=2.7.4&appKey=12574478&t=' + ts + '&sign=' + token_part + '&api=' + api + '&v=1.0&type=jsonp&dataType=jsonp&timeout=20000';
                    const resp = await fetch(url, {
                        method: 'POST',
                        credentials: 'include',
                        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                        body: 'data=' + encodeURIComponent(JSON.stringify({})),
                    });
                    const text = await resp.text();
                    return { ok: true, status: resp.status, body: text.substring(0, 800) };
                } catch (e) {
                    return { ok: false, error: String(e) };
                }
            }""")
            if mtop_result and mtop_result.get("ok"):
                body = mtop_result.get("body", "")
                log(f"[silent] MTOP API 响应: status={mtop_result.get('status')} body={body[:1500]}")
                if "FAIL_SYS_USER_VALIDATE" in body or "RGV587_ERROR" in body:
                    log(f"[silent] ✓ MTOP API 触发 Baxia 验证")
                    # 尝试从响应中提取验证 URL
                    import json as _json
                    try:
                        # JSONP 响应可能需要解析
                        # 尝试直接 JSON 解析
                        try:
                            resp_data = _json.loads(body)
                        except Exception:
                            # 尝试 JSONP 解析
                            import re as _re
                            m = _re.search(r'\{.*\}', body)
                            if m:
                                resp_data = _json.loads(m.group(0))
                            else:
                                resp_data = {}

                        # 检查 data.url（Baxia 验证 URL）
                        data_obj = resp_data.get("data", {}) if isinstance(resp_data, dict) else {}
                        verify_url = data_obj.get("url") or data_obj.get("validateUrl") or ""
                        if not verify_url:
                            # 有些响应把 url 放在 ret 中
                            ret_list = resp_data.get("ret", []) if isinstance(resp_data, dict) else []
                            for r in ret_list:
                                if isinstance(r, str) and "http" in r:
                                    verify_url = r
                                    break

                        if verify_url:
                            log(f"[silent] 发现 Baxia 验证 URL: {verify_url[:200]}")
                            # 在新 iframe 中加载验证 URL，让 Baxia JS 自动处理
                            try:
                                # 方案 1: 直接 page.goto 验证 URL
                                await page.goto(verify_url, wait_until="domcontentloaded", timeout=15000)
                                log(f"[silent] 导航到验证 URL 后页面 URL: {page.url[:200]}")
                                # 等待 Baxia JS 静默验证
                                await asyncio.sleep(3)
                                # 检查 x5sec
                                try:
                                    all_cookies = await ctx.cookies()
                                    for c in all_cookies:
                                        if c.get("name") == "x5sec" and c.get("value"):
                                            captured_x5sec["value"] = c["value"]
                                            captured_x5sec["source"] = "verify_url_nav"
                                            log(f"[silent] ✓ 从验证 URL 导航后获取到 x5sec (长度={len(c['value'])})")
                                            break
                                except Exception as e:
                                    log(f"[silent] 验证 URL 后 ctx.cookies() 异常: {e}")
                            except Exception as e:
                                log(f"[silent] 导航验证 URL 异常: {e}")
                        else:
                            log(f"[silent] 响应中未找到验证 URL，尝试 JSONP 完整解析...")
                            log(f"[silent] 完整响应: {body[:2000]}")
                    except Exception as e:
                        log(f"[silent] 解析 MTOP 响应异常: {e}")
                        log(f"[silent] 完整响应: {body[:2000]}")

                    # 检查页面是否有 Baxia iframe 或验证元素
                    try:
                        baxia_info = await page.evaluate("""() => {
                            const iframes = document.querySelectorAll('iframe');
                            const iframe_info = [];
                            for (const f of iframes) {
                                iframe_info.push({src: f.src || '', id: f.id || '', name: f.name || ''});
                            }
                            // 检查是否有 nocaptcha 或 baxia 相关元素
                            const nc = document.querySelector('#nc_1_wrapper, .nc-container, [data-nc], .baxia-dialog');
                            return {
                                iframes: iframe_info,
                                hasNocaptcha: !!nc,
                                ncHtml: nc ? nc.outerHTML.substring(0, 200) : null,
                                title: document.title,
                                url: location.href,
                            };
                        }""")
                        log(f"[silent] 页面 Baxia 元素: iframes={len(baxia_info.get('iframes', []))} hasNocaptcha={baxia_info.get('hasNocaptcha')} title={baxia_info.get('title')}")
                        for ii, iframe in enumerate(baxia_info.get("iframes", [])[:5]):
                            log(f"[silent] iframe[{ii}]: src={iframe.get('src', '')[:150]} id={iframe.get('id')}")
                        if baxia_info.get("ncHtml"):
                            log(f"[silent] nocaptcha HTML: {baxia_info['ncHtml']}")
                    except Exception as e:
                        log(f"[silent] 检查 Baxia 元素异常: {e}")

                    # 2026-08-02 关键修复：MTOP API 返回 FAIL_SYS_USER_VALIDATE 但未获取到 x5sec
                    # 说明账号已被 Baxia punish，静默验证无法通过，必须拖滑块才能解除
                    # 不再等待 15 秒超时，立即返回 punished 让上层快速降级到滑块求解
                    if not captured_x5sec["value"]:
                        log(f"[silent] ⚠ MTOP API 返回 FAIL_SYS_USER_VALIDATE 但未获取到 x5sec，账号被 punish，立即降级到滑块求解")
                        result["source"] = "punished"
                        result["error"] = "账号被 Baxia punish（MTOP API 返回 FAIL_SYS_USER_VALIDATE，未获取 x5sec），需降级到滑块求解"
                        result["durationMs"] = int((time.time() - start_time) * 1000)
                        return result

                    log(f"[silent] 等待 Baxia JS 静默验证设置 x5sec...")
                elif '"token"' in body or "tokenInfo" in body:
                    log(f"[silent] ✓ MTOP API 直接返回 token（无需 Baxia 验证）")
                    # 直接成功，从 cookie 提取 x5sec
                    try:
                        all_cookies = await ctx.cookies()
                        for c in all_cookies:
                            if c.get("name") == "x5sec" and c.get("value"):
                                captured_x5sec["value"] = c["value"]
                                captured_x5sec["source"] = "ctx_cookies_after_mtop"
                                log(f"[silent] ✓ MTOP API 调用后从 cookie 获取到 x5sec (长度={len(c['value'])})")
                                break
                    except Exception as e:
                        log(f"[silent] MTOP API 后 ctx.cookies() 异常: {e}")
                else:
                    log(f"[silent] MTOP API 响应未识别，继续等待 x5sec...")
                    log(f"[silent] 完整响应: {body[:2000]}")
            else:
                log(f"[silent] MTOP API 调用失败: {mtop_result}")
        except Exception as e:
            log(f"[silent] MTOP API 调用异常: {e}")

        if "punish" in current_url.lower() or "deny" in current_url.lower():
            result["source"] = "punished"
            result["error"] = f"账号被 punish，静默验证无法通过（URL={current_url[:100]}）"
            log(f"[silent] ⚠ 账号被 punish: {current_url[:100]}")
        else:
            # 等待 Baxia JS 静默验证完成并设置 x5sec
            for i in range(timeout_sec):
                if captured_x5sec["value"]:
                    break
                await asyncio.sleep(1)
                # 每 3 秒轮询 cookie，弥补 Set-Cookie 头未捕获的情况
                if i % 3 == 2:
                    try:
                        all_cookies = await ctx.cookies()
                        for c in all_cookies:
                            if c.get("name") == "x5sec" and c.get("value"):
                                captured_x5sec["value"] = c["value"]
                                captured_x5sec["source"] = f"ctx_cookies_poll_{i+1}s"
                                log(f"[silent] ✓ 轮询 cookie 获取到 x5sec (长度={len(c['value'])})")
                                break
                    except Exception:
                        pass
                log(f"[silent] 等待 x5sec... ({i+1}/{timeout_sec}s)")

            if captured_x5sec["value"]:
                result["ok"] = True
                result["x5sec"] = captured_x5sec["value"]
                result["source"] = captured_x5sec["source"] or "set_cookie_header"
                log(f"[silent] ✓ 通过 HTTP 拦截器获取到 x5sec (长度={len(result['x5sec'])})")
            else:
                try:
                    all_cookies = await ctx.cookies()
                    for c in all_cookies:
                        if c.get("name") == "x5sec" and c.get("value"):
                            result["ok"] = True
                            result["x5sec"] = c["value"]
                            result["source"] = "ctx_cookies"
                            log(f"[silent] ✓ 通过 ctx.cookies() 获取到 x5sec (长度={len(result['x5sec'])})")
                            break
                except Exception as e:
                    log(f"[silent] ctx.cookies() 异常: {e}")

                if not result["ok"]:
                    result["source"] = "timeout"
                    result["error"] = f"静默验证超时（{timeout_sec}s内未获取到 x5sec，账号可能被 punish 或指纹被识别）"
                    log(f"[silent] ⚠ 静默提取超时（{timeout_sec}s）")

    except Exception as e:
        log(f"[silent] 静默提取异常: {e}")
        result["source"] = "error"
        result["error"] = f"静默提取异常: {e}"
    finally:
        if ctx:
            try:
                await ctx.close()
            except Exception:
                pass
        if profile_strategy != "persistent":
            try:
                shutil.rmtree(user_data_dir, ignore_errors=True)
            except Exception:
                pass

    result["durationMs"] = int((time.time() - start_time) * 1000)
    return result


async def _launch_solve_once(
    playwright,
    chrome_path: str,
    ua: str,
    cookie_str: str,
    target_url: str,
    max_retries: int,
    proxy: Optional[dict] = None,
    profile_strategy: str = "persistent",
    semi_auto_fallback: bool = False,
) -> dict:
    """启动一次浏览器并求解（内部复用）。

    Args:
        profile_strategy: profile 选择策略
            - persistent: 持久化 profile（累积历史/cookie/指纹，最大程度模拟真人）
            - seed: 克隆预热 seed profile（fallback）
            - temp: 临时空 profile（最不安全，仅用于对比测试）
        semi_auto_fallback: 全自动失败后是否保留窗口供人工拖拽
    """
    user_data_dir = _resolve_profile_dir(profile_strategy, cookie_str=cookie_str)
    is_persistent = profile_strategy == "persistent"
    # seed/temp 策略需要克隆/清理；persistent 不清理（保留历史）
    if not is_persistent:
        prepare_profile_dir(user_data_dir)
    ctx = None
    try:
        log(
            f"=== 启动真实 Chrome（profile={profile_strategy} patchright={_USING_PATCHRIGHT}"
            f" hasProxy={bool(proxy and proxy.get('server'))} ==="
        )
        if _USING_PATCHRIGHT:
            # patchright 模式：patchright 自动清理 CDP 痕迹（cdc_/__playwright__/webdriver），
            # 自动处理 navigator.webdriver / window.chrome。
            # 2026-08-01 重大修复：必须设置 user_agent=ua（Windows UA）
            # 原因：patchright 在 Linux 容器中用真实 Chrome UA（X11; Linux x86_64），
            #       但 _ADVANCED_FINGERPRINT_SCRIPT 设置 userAgentData.platform='Windows'，
            #       导致 UA 与 Client Hints 平台矛盾，Baxia FireyeJS 直接判定为机器人，
            #       这是滑块求解 0% 成功率的根本原因。
            #       修复后统一用 Windows UA + Windows Client Hints + navigator.platform='Win32'。
            # 不注入 STEALTH_INIT_SCRIPT（会与 patchright 冲突，引入 toString 检测漏洞），
            # 不用 ignore_default_args（patchright 自动处理 --enable-automation）。
            # 只保留 patchright 不处理的高级指纹规避（WebGL/Canvas/Audio）。
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
                user_agent=ua,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
                    # 2026-08-01 优化：窗口固定在屏幕左上角，配合 xdotool 系统级鼠标拖动
                    # 原因：xdotool 用 X11 屏幕坐标，需要知道浏览器窗口在屏幕中的位置。
                    #       --window-position=0,0 让窗口在左上角，视口坐标到屏幕坐标的偏移最小。
                    "--window-position=0,0",
                    "--lang=zh-CN",
                    # 2026-08-01 修复：去掉 swiftshader（导致 page.mouse 卡住），
                    # 改用 _ADVANCED_FINGERPRINT_SCRIPT 里 patch getContext 返回假 WebGL 上下文。
                    # swiftshader 软件渲染会让页面响应极慢，page.mouse.move 卡住 10s+。
                ],
            )
        else:
            # playwright 模式：保留原有反检测逻辑（STEALTH_INIT_SCRIPT + stealth_args）
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
                viewport={"width": WINDOW_WIDTH, "height": WINDOW_HEIGHT},
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
                user_agent=ua,
                color_scheme="light",
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                ignore_default_args=["--enable-automation"],
                args=_chrome_stealth_args(),
            )
        if proxy and proxy.get("server"):
            launch_kwargs["proxy"] = {
                "server": str(proxy["server"]),
                **({"username": str(proxy["username"])} if proxy.get("username") else {}),
                **({"password": str(proxy["password"])} if proxy.get("password") else {}),
            }
        try:
            ctx = await playwright.chromium.launch_persistent_context(**launch_kwargs)
        except Exception as e:
            log(f"launch_persistent_context 失败，重试精简参数: {e}")
            launch_kwargs.pop("timezone_id", None)
            launch_kwargs["args"] = [
                "--no-first-run",
                "--disable-blink-features=AutomationControlled",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
            ]
            ctx = await playwright.chromium.launch_persistent_context(**launch_kwargs)

        # playwright 模式注入完整 STEALTH_INIT_SCRIPT；patchright 模式只注入高级指纹规避
        if _USING_PATCHRIGHT:
            await ctx.add_init_script(_ADVANCED_FINGERPRINT_SCRIPT)
            log("✓ patchright 模式：已注入高级指纹规避（WebGL/Canvas/Audio），CDP 痕迹由 patchright 自动清理")
        else:
            await ctx.add_init_script(STEALTH_INIT_SCRIPT)

        page0 = ctx.pages[0] if ctx.pages else await ctx.new_page()
        # 先落到业务域再注入 Cookie，避免 add_cookies 被丢弃
        try:
            await page0.goto("https://www.goofish.com/", wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            log(f"预热域导航警告: {e}")
        # 清除风控相关 cookie（x5sectag/x5sec/tfstk 等），让服务器重新评估会话，
        # 避免带着 punish 标记访问导致持续被风控。
        clean_cookie_str = strip_risk_cookies(cookie_str)
        cookies = parse_cookie_string(clean_cookie_str, ".goofish.com")
        # 同步 www 主机 cookie，提高会话命中
        cookies += parse_cookie_string(clean_cookie_str, "www.goofish.com")
        if cookies:
            try:
                await ctx.add_cookies(cookies)
                log(f"注入 {len(cookies)} 条 cookies（含 .goofish / www）")
            except Exception as e:
                log(f"注入 cookies 警告: {e}")
                # 回退只写 .goofish.com
                try:
                    await ctx.add_cookies(parse_cookie_string(clean_cookie_str, ".goofish.com"))
                except Exception:
                    pass
        try:
            await page0.reload(wait_until="domcontentloaded", timeout=45000)
        except Exception:
            pass

        # 强制修复指纹（add_init_script 可能被 patchright 覆盖，用 page.evaluate 在页面加载后直接修复）
        # 关键：Baxia 在页面加载时检测 window.chrome.runtime，必须在检测前修复
        if _USING_PATCHRIGHT:
            try:
                await page0.evaluate(_ADVANCED_FINGERPRINT_SCRIPT)
                fix_check = await page0.evaluate(
                    """() => ({
                        chrome: !!(window.chrome && window.chrome.runtime),
                        languages: navigator.languages,
                        voices: (window.speechSynthesis && window.speechSynthesis.getVoices && window.speechSynthesis.getVoices().length) || 0,
                    })"""
                )
                log(f"指纹强制修复结果: {fix_check}")
            except Exception as e:
                log(f"指纹强制修复异常: {e}")

        # 指纹诊断探针：在求解前打印当前浏览器环境的机器人特征信号
        try:
            await _log_fingerprint_probe(page0, label="pre-solve")
        except Exception as e:
            log(f"指纹探针调用异常（不影响后续流程）: {e}")

        # Cookie 落地后拟人闲逛，降低"秒进消息页"特征
        # 增强：4-7 次鼠标移动 + 2-4 次滚动 + 30% 概率访问商品页
        warm = 3.0 + random.random() * 3.0
        log(f"Cookie 预热闲逛 {warm:.1f}s ...")
        await asyncio.sleep(warm)
        try:
            mouse_moves = random.randint(4, 7)
            for i in range(mouse_moves):
                await page0.mouse.move(
                    100 + random.random() * 800,
                    120 + random.random() * 400,
                    steps=random.randint(8, 16),
                )
                await asyncio.sleep(0.2 + random.random() * 0.4)
            # 多次滚动，模拟真人浏览
            scroll_count = random.randint(2, 4)
            for _ in range(scroll_count):
                await page0.mouse.wheel(0, 200 + random.randint(0, 400))
                await asyncio.sleep(0.4 + random.random() * 0.6)
            # 30% 概率访问一个商品页，增加真实浏览痕迹
            # 搜索上下文（punish URL）跳过此步骤：
            #   1. 搜索场景访问固定商品页反而可疑（每次搜索都访问同一商品）
            #   2. 商品页可能慢或下架，30 秒 goto + 30 秒 go_back 浪费 60 秒
            #   3. 搜索上下文已通过 punish URL 直接 goto，不需要额外浏览痕迹
            # 消息页上下文保留此步骤（增加真实浏览历史，降低"秒进消息页"特征）
            if not _is_punish_url(target_url) and random.random() < 0.3:
                try:
                    sample_url = "https://www.goofish.com/item?itemId=746285119876"
                    log(f"访问商品页增加浏览痕迹: {sample_url}")
                    await page0.goto(sample_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(1.5 + random.random() * 1.5)
                    # 滚动一下商品页
                    await page0.mouse.wheel(0, 300 + random.randint(0, 500))
                    await asyncio.sleep(0.8 + random.random() * 0.8)
                    # 返回首页
                    await page0.go_back(wait_until="domcontentloaded", timeout=30000)
                except Exception as e:
                    log(f"商品页访问警告（不影响后续）: {e}")
            elif _is_punish_url(target_url):
                log("搜索上下文（punish URL），跳过商品页访问以节省时间")
        except Exception:
            pass
        await asyncio.sleep(0.8 + random.random() * 1.0)

        solve_result = await solve_in_context(ctx, target_url, max_retries)
        # 2026-08-02 修复：从 solve_in_context 传回的 captured_x5sec 中恢复 x5sec
        captured_x5sec_val = solve_result.pop("captured_x5sec", "") or ""
        if captured_x5sec_val and not solve_result.get("x5sec"):
            solve_result["x5sec"] = captured_x5sec_val
            log(f"🔑 [x5sec] 从 HTTP 响应拦截器恢复成功! value长度={len(captured_x5sec_val)}")

        if solve_result.get("solved"):
            # solve_in_context 内部已通过 _collect_cookies_and_x5sec 提取了 cookies/x5sec
            # 这里作为补充：如果 ctx 仍可用，重新提取最新 cookies
            try:
                fresh = await export_cookies(ctx)
                if fresh:
                    solve_result["cookies"] = fresh
                    solve_result["cookieCount"] = fresh.count("=")
                    log(f"导出 {solve_result['cookieCount']} 个最新 cookies（{len(fresh)} 字符）")
            except Exception as e:
                log(f"export_cookies 失败（ctx 可能已关闭，使用内部提取的 cookies）: {e}")
            # 提取 x5sec（仅在缺失时补充）
            if not solve_result.get("x5sec"):
                try:
                    x5sec = await extract_x5sec(ctx)
                    if x5sec:
                        solve_result["x5sec"] = x5sec
                except Exception:
                    pass
            # 兜底：从 cookies 字符串提取 x5sec
            if not solve_result.get("x5sec") and solve_result.get("cookies"):
                m = re.search(r"(?:^|;\s*)x5sec=([^;]+)", solve_result["cookies"])
                if m and m.group(1):
                    solve_result["x5sec"] = m.group(1)
                    log(f"🔑 [x5sec] 从 cookies 字符串中提取成功! value长度={len(m.group(1))}")
            if solve_result.get("x5sec"):
                log(f"🔑 [x5sec] 最终获取成功! value长度={len(solve_result['x5sec'])}")
            else:
                log("⚠ [x5sec] 未能获取 x5sec，WS 重连时无法免滑块恢复")
            return solve_result

        # 全自动失败 → 半自动人工兜底（保留窗口供人工拖拽）
        if semi_auto_fallback and solve_result.get("captchaDetected") and not solve_result.get("isLoginPage"):
            log("全自动求解失败，尝试半自动人工兜底...")
            solve_result = await _semi_auto_human_fallback(ctx, solve_result, timeout_sec=120)
            if solve_result.get("solved"):
                return solve_result

        # 2026-08-02 修复：即使求解失败，如果拦截器捕获了 x5sec，也记录日志
        if solve_result.get("x5sec"):
            log(f"🔑 [x5sec] 求解失败但拦截器捕获到 x5sec! value长度={len(solve_result['x5sec'])}，仍可缓存用于免滑块")
        return solve_result
    finally:
        if ctx is not None:
            try:
                await ctx.close()
            except Exception:
                pass
        # 持久化 profile 不删除（保留浏览历史/cookie/指纹）
        # seed/temp 策略清理临时目录
        if not is_persistent:
            try:
                shutil.rmtree(user_data_dir, ignore_errors=True)
            except Exception:
                pass


async def main_async(args) -> dict:
    """全自动求解入口（可选半自动人工介入）。

    策略：
    1) 全局文件锁：同时只允许 1 个求解浏览器
    2) persistent profile 持久化：累积历史/cookie/指纹，最大程度模拟真人
    3) 真实 Chrome + 去 enable-automation + stealth 增强（22+ 检测点覆盖）
    4) 拟人进消息页 + 多策略拖拽（仅浏览器内 page.mouse，不控制系统鼠标）
    5) 首轮全失败后，换 seed profile 再全自动重开一轮
    6) 半自动人工兜底（可选）：两轮全自动均失败后保留窗口供人工拖拽
    """
    start_time = time.time()
    result: dict[str, Any] = {
        "ok": False,
        "solved": False,
        "captchaDetected": False,
        "attempts": 0,
        "durationMs": 0,
    }

    try:
        with open(args.cookie_file, "r", encoding="utf-8") as f:
            cookie_str = f.read().strip()
    except Exception as e:
        result["error"] = f"读取 Cookie 文件失败: {e}"
        result["durationMs"] = int((time.time() - start_time) * 1000)
        return result

    if not cookie_str:
        result["error"] = "Cookie 字符串为空"
        result["durationMs"] = int((time.time() - start_time) * 1000)
        return result

    # 2026-08-02 x5sec 主方案：静默提取模式（--silent-extract）
    # 不拖滑块，依赖浏览器 Baxia JS 静默验证获取 x5sec（8s 超时）
    # 详见 .trae/rules/x5sec-research-knowledge.md 方案 B
    if bool(getattr(args, "silent_extract", False)):
        log("=== 静默 x5sec 提取模式（--silent-extract）===")
        try:
            _chrome = find_chrome_path()
            if not _chrome:
                result["error"] = "未找到 Chrome 可执行文件"
                result["durationMs"] = int((time.time() - start_time) * 1000)
                return result
            _ua = get_chrome_user_agent(_chrome)
            _proxy = None
            if getattr(args, "proxy_server", ""):
                _proxy = {"server": args.proxy_server}
                if getattr(args, "proxy_username", ""):
                    _proxy["username"] = args.proxy_username
                if getattr(args, "proxy_password", ""):
                    _proxy["password"] = args.proxy_password
            # 注意：async_playwright 已在模块顶部全局导入（patchright 优先，playwright 兜底）
            # 不得在此处局部 import，否则会让 Python 把 async_playwright 当作 main_async 的局部变量，
            # 导致非静默流程（main_async 末尾的 async with async_playwright()）报错：
            # "cannot access local variable 'async_playwright' where it is not associated with a value"
            async with async_playwright() as p:
                silent_result = await silent_extract_x5sec(
                    playwright=p,
                    chrome_path=_chrome,
                    ua=_ua,
                    cookie_str=cookie_str,
                    target_url=getattr(args, "target_url", "https://www.goofish.com/im"),
                    proxy=_proxy,
                    profile_strategy=getattr(args, "profile_strategy", "temp"),
                    timeout_sec=15,
                )
            result.update(silent_result)
            result["ok"] = silent_result.get("ok", False)
            result["durationMs"] = int((time.time() - start_time) * 1000)
            log(f"静默提取完成: ok={result['ok']} source={silent_result.get('source', '')} x5sec_len={len(silent_result.get('x5sec', ''))}")
            return result
        except Exception as e:
            log(f"静默提取异常: {e}")
            result["error"] = f"静默提取异常: {e}"
            result["durationMs"] = int((time.time() - start_time) * 1000)
            return result

    chrome_path = find_chrome_path()
    if not chrome_path:
        result["error"] = "未找到 Chrome 可执行文件"
        result["durationMs"] = int((time.time() - start_time) * 1000)
        return result

    ua = get_chrome_user_agent(chrome_path)
    log(f"Chrome 路径: {chrome_path}")
    log(f"UA: {ua}")

    # 读取 CLI 参数（支持命令行调用和外部直接调用两种方式）
    profile_strategy = getattr(args, "profile_strategy", "persistent") or "persistent"
    semi_auto_fallback = bool(getattr(args, "semi_auto_fallback", False))
    log(f"求解配置: profile_strategy={profile_strategy} semi_auto_fallback={semi_auto_fallback}")

    try:
        # 2026-08-01 优化：移除 _FileLock 全局锁，允许 2 个 Python 进程并行
        # 原因：全局锁导致第二个请求等锁 60 秒后超时失败，6 个活跃账号只有 1 个能求解。
        #       每个进程使用独立的 temp profile 目录（chrome-slider-temp-*），不冲突。
        #       服务器有 16GB 内存，支持 2 个 Chrome 进程并行。
        #       server.ts 层面有 MAX_PYTHON_FALLBACK_CONCURRENCY=2 控制并发上限。
        log("跳过全局锁（已移除），直接启动求解")
        ensure_temp_space()
        async with async_playwright() as p:
            await ensure_seed_profile(p, chrome_path, ua)

            proxy_cfg = None
            if getattr(args, "proxy_server", None):
                proxy_cfg = {
                    "server": args.proxy_server,
                    "username": getattr(args, "proxy_username", None) or None,
                    "password": getattr(args, "proxy_password", None) or None,
                }
                log(f"使用绑定代理 server={args.proxy_server}")

            # 第一轮：使用配置的 profile 策略
            # 半自动兜底只在第一轮启用（避免第二轮重复等待人工）
            r1 = await _launch_solve_once(
                p, chrome_path, ua, cookie_str, args.target_url, args.max_retries,
                proxy=proxy_cfg,
                profile_strategy=profile_strategy,
                semi_auto_fallback=semi_auto_fallback,
            )
            result.update(r1)
            total_attempts = int(r1.get("attempts") or 0)

            # 第二轮：已禁用
            # 2026-08-01 修复：实测第一轮约 77-90s（含 seed 预热 + 导航 + 拖动），
            # 第二轮换 profile 重开浏览器至少需要 30-40s，120s 超时下必然超时。
            # 超时后 stdout 为空，无法调试，且浪费 40s 算力。
            # 改为：第一轮 max_retries=4，专注在单轮内多次拖动尝试。
            # 如果未来需要第二轮，应在 server.ts 把超时提高到 180s 以上。
            result["attempts"] = total_attempts or result.get("attempts") or 0

    except TimeoutError as e:
        result["error"] = str(e)
    except Exception as e:
        log(f"主流程异常: {e}")
        result["error"] = f"求解异常: {e}"

    result["durationMs"] = int((time.time() - start_time) * 1000)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="闲鱼滑块验证自动求解器")
    parser.add_argument("--cookie-file", required=True, help="Cookie 字符串文件路径")
    parser.add_argument("--target-url", default=DEFAULT_TARGET_URL, help="目标页面 URL")
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES, help="最大拖动重试次数")
    parser.add_argument("--proxy-server", default="", help="账号绑定代理 server，如 http://host:port")
    parser.add_argument("--proxy-username", default="", help="代理用户名")
    parser.add_argument("--proxy-password", default="", help="代理密码")
    parser.add_argument(
        "--profile-strategy",
        default="persistent",
        choices=["persistent", "seed", "temp"],
        help="profile 选择策略：persistent（持久化，默认）/ seed（克隆预热）/ temp（临时空）",
    )
    parser.add_argument(
        "--semi-auto-fallback",
        action="store_true",
        help="全自动失败后保留浏览器窗口供人工拖拽（120 秒超时）",
    )
    parser.add_argument(
        "--silent-extract",
        action="store_true",
        help="静默 x5sec 提取模式：不拖滑块，依赖浏览器 Baxia JS 静默验证获取 x5sec（8s 超时）",
    )
    args = parser.parse_args()
    result = asyncio.run(main_async(args))
    output_result(result)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
