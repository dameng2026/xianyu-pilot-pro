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

    // ===== 5. navigator.userAgentData (Client Hints) — Chrome 131+ 必有 =====
    // Playwright 不自动设置 UA-CH，Baxia 检测 navigator.userAgentData 是否存在且与 UA 一致
    if (!navigator.userAgentData) {
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

    // ===== 7. WebGL vendor/renderer（保留真实 GPU 信息，不修改） =====
    // 注意：之前修改为 NVIDIA GTX 1660 SUPER，但实际 GPU 是 AMD Radeon RX 7700 XT，
    // 修改会导致 WebGL 指纹与实际 GPU 不一致，反而更可疑。
    // patchright 用真实 Chrome，WebGL 指纹是真实的，不需要修改。

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

SUCCESS_SELECTORS = [".nc_ok", ".success", "#nc_1_n1z.success", ".icon-success"]
FAIL_SELECTORS = [".nc_error", ".errloading", ".fail", "#nc_1_refresh1"]


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
        import msvcrt  # Windows

        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._fh = open(self.path, "a+b")
        start = time.time()
        while True:
            try:
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"等待滑块全局锁超时: {self.path}")
                time.sleep(0.5)

    def __exit__(self, *args):
        try:
            import msvcrt

            if self._fh:
                try:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
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
    """基于元素 hover 的 page.mouse 拖动：先悬停按钮再按下，减少“点空”。"""
    box = await button.bounding_box()
    if not box:
        raise RuntimeError("button box gone")
    sx = box["x"] + box["width"] / 2
    sy = box["y"] + box["height"] / 2
    # attempt 调制终点：1 精确、2 略超、3 略欠
    if attempt % 3 == 1:
        dist = distance
    elif attempt % 3 == 2:
        dist = distance + 3 + random.random() * 5
    else:
        dist = max(180.0, distance - 2 + random.random() * 4)

    log(f"  元素悬停拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} attempt={attempt}")
    await button.hover(timeout=3000)
    await asyncio.sleep(0.15 + random.random() * 0.25)
    await page.mouse.move(sx, sy, steps=3)
    await asyncio.sleep(0.08 + random.random() * 0.12)
    await page.mouse.down()
    await asyncio.sleep(0.1 + random.random() * 0.15)

    steps = 36 + random.randint(0, 16)
    for i in range(1, steps + 1):
        p = i / steps
        if p < 0.22:
            eased = 0.1 * (p / 0.22) ** 2.2
        elif p < 0.78:
            mid = (p - 0.22) / 0.56
            eased = 0.1 + 0.75 * (mid * mid * (3 - 2 * mid))
        else:
            tail = (p - 0.78) / 0.22
            eased = 0.85 + 0.15 * math.sin(tail * math.pi / 2)
        x = sx + dist * eased
        # Y 抖动控制在 ±3px，过大易被判机器人
        y = sy + math.sin(math.pi * p) * (1.2 + random.random() * 2.0) * (1 if random.random() > 0.5 else -1)
        await page.mouse.move(x, y, steps=1)
        delay = 18 + random.random() * 42
        if p < 0.2 or p > 0.85:
            delay *= 1.7
        await page.wait_for_timeout(delay)

    await page.mouse.move(sx + dist, sy + random.uniform(-1.5, 1.5), steps=2)
    await page.wait_for_timeout(60 + random.random() * 80)
    await page.mouse.up()
    await page.wait_for_timeout(40 + random.random() * 60)


def _bezier_points(p0, p1, p2, p3, n: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


async def bezier_mouse_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """三次贝塞尔拟人拖动（仅 page.mouse，X 近似单调递增）。"""
    dist = distance + random.uniform(-2, 4)
    sx = start_x + random.uniform(-2, 2)
    sy = start_y + random.uniform(-1.5, 1.5)
    ex = sx + dist
    ey = sy + random.uniform(-2, 2)
    # 控制点：中段轻微弧线，幅度 2~6px
    amp = (2 + random.random() * 4) * (1 if random.random() > 0.5 else -1)
    c1 = (sx + dist * 0.25, sy + amp * 0.6)
    c2 = (sx + dist * 0.7, sy + amp)
    steps = 40 + random.randint(0, 20)
    log(f"  贝塞尔拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} steps={steps} attempt={attempt}")

    # 接近
    await page.mouse.move(sx - 30 - random.random() * 40, sy + random.uniform(-15, 15), steps=8)
    await page.wait_for_timeout(80 + random.random() * 120)
    await page.mouse.move(sx, sy, steps=6)
    await page.wait_for_timeout(100 + random.random() * 150)
    await page.mouse.down()
    await page.wait_for_timeout(90 + random.random() * 100)

    pts = _bezier_points((sx, sy), c1, c2, (ex, ey), steps)
    last_x = sx
    for i, (x, y) in enumerate(pts):
        # 强制 X 不回退超过 1px（Baxia 对大幅回退敏感）
        if x < last_x - 1:
            x = last_x + random.uniform(0.5, 1.5)
        await page.mouse.move(x, y, steps=1)
        p = (i + 1) / steps
        delay = 16 + random.random() * 38
        if p < 0.2 or p > 0.82:
            delay *= 1.75
        await page.wait_for_timeout(delay)
        last_x = x

    await page.mouse.move(ex, ey + random.uniform(-1, 1), steps=2)
    await page.wait_for_timeout(70 + random.random() * 90)
    await page.mouse.up()
    await page.wait_for_timeout(50 + random.random() * 70)


async def microstep_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """小步匀加速拖动：每步 2~4px，总时长约 1.2~2.2s，贴近部分真人习惯。"""
    sx = start_x + random.uniform(-1.5, 1.5)
    sy = start_y + random.uniform(-1, 1)
    dist = distance + random.uniform(-1, 3)
    log(f"  微步拖动: start=({sx:.1f},{sy:.1f}) dist={dist:.1f} attempt={attempt}")
    await page.mouse.move(sx, sy, steps=5)
    await page.wait_for_timeout(120 + random.random() * 100)
    await page.mouse.down()
    await page.wait_for_timeout(80 + random.random() * 80)
    moved = 0.0
    while moved < dist:
        # 前慢后略快
        ratio = moved / dist if dist else 1
        step = 2.0 + random.random() * 2.5
        if ratio < 0.2:
            step *= 0.55
        elif ratio > 0.75:
            step *= 0.7
        step = min(step, dist - moved)
        moved += step
        y = sy + random.uniform(-1.2, 1.2)
        await page.mouse.move(sx + moved, y, steps=1)
        await page.wait_for_timeout(12 + random.random() * 22)
    await page.mouse.move(sx + dist, sy, steps=1)
    await page.wait_for_timeout(50 + random.random() * 60)
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


async def check_solved(page) -> bool:
    for sel in SUCCESS_SELECTORS:
        for frame in page.frames:
            try:
                elem = await frame.query_selector(sel)
                if elem and await elem.is_visible():
                    return True
            except Exception:
                pass
    for sel in FAIL_SELECTORS:
        for frame in page.frames:
            try:
                elem = await frame.query_selector(sel)
                if elem and await elem.is_visible():
                    return False
            except Exception:
                pass
    detected, _ = await detect_captcha_container(page)
    return not detected


async def human_like_drag(page, start_x: float, start_y: float, distance: float, attempt: int = 1) -> None:
    """容器内拖动：接近轨迹 + 起点偏移 + 三阶段速度 + Y 弧线 + 过冲回退。"""
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

    # 起点在按钮中心附近随机偏移（±4px），避免永远点死中心
    actual_start_x = start_x + random.uniform(-4, 4)
    actual_start_y = start_y + random.uniform(-3, 3)

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
        actual_start_x + random.uniform(-2, 2),
        actual_start_y + random.uniform(-2, 2),
    )
    await page.wait_for_timeout(40 + random.random() * 60)

    arc_direction = -1 if random.random() < 0.5 else 1
    arc_amplitude = 3 + random.random() * 6
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
        target_x = actual_start_x + distance * eased

        # 中段偶发回退
        if random.random() < 0.06 and 3 < i < steps - 4:
            target_x = last_x - (2 + random.random() * 4)

        arc_offset = arc_direction * arc_amplitude * math.sin(math.pi * progress)
        y_drift = (random.random() - 0.5) * 5
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

    # 过冲 + 回退 + 微调释放
    await page.wait_for_timeout(40 + random.random() * 80)
    overshoot = 6 + random.random() * 10
    await page.mouse.move(
        actual_start_x + distance + overshoot,
        actual_start_y + random.uniform(-6, 6),
        steps=2,
    )
    await page.wait_for_timeout(60 + random.random() * 90)
    await page.mouse.move(
        actual_start_x + distance + random.uniform(-1.5, 1.5),
        actual_start_y + random.uniform(-3, 3),
        steps=2,
    )
    for _ in range(1 if random.random() < 0.65 else 2):
        await page.wait_for_timeout(45 + random.random() * 70)
        await page.mouse.move(
            actual_start_x + distance + random.uniform(-2, 2),
            actual_start_y + random.uniform(-2, 2),
        )
    await page.wait_for_timeout(60 + random.random() * 90)
    await page.mouse.up()


async def human_like_drag_out_of_container(
    page, start_x: float, start_y: float, distance: float, attempt: int = 1
) -> None:
    """出容器拖动：Y 大幅偏出弹窗（±50~120px），模拟真人不拘束手部路径。"""
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

    actual_start_x = start_x + random.uniform(-3, 3)
    actual_start_y = start_y + random.uniform(-2, 2)

    await page.mouse.move(actual_start_x - 30 - random.random() * 40, actual_start_y + random.uniform(-20, 20))
    await page.wait_for_timeout(80 + random.random() * 120)
    await page.mouse.move(actual_start_x, actual_start_y, steps=6)
    await page.wait_for_timeout(100 + random.random() * 150)
    await page.mouse.down()
    await page.wait_for_timeout(90 + random.random() * 110)

    num_out_points = 2 + random.randint(0, 1)
    out_points = []
    for i in range(num_out_points):
        prog = 0.2 + (0.6 * (i + 1) / (num_out_points + 1)) + random.uniform(-0.05, 0.05)
        direction = -1 if i % 2 == 0 else 1
        magnitude = 55 + random.random() * 70
        out_points.append({"progress": max(0.15, min(0.85, prog)), "y_offset": direction * magnitude})
    log(
        "  出容器拐点: "
        + " | ".join(f"p={p['progress']:.2f},y={p['y_offset']:.0f}px" for p in out_points)
    )

    last_x = actual_start_x
    for i in range(1, steps + 1):
        progress = i / steps
        eased = progress * progress * (3 - 2 * progress)
        target_x = actual_start_x + distance * eased
        if random.random() < 0.05 and 3 < i < steps - 3:
            target_x = last_x - (2 + random.random() * 3)

        base_arc = math.sin(math.pi * progress) * 5
        y_offset = 0.0
        for op in out_points:
            dist = abs(progress - op["progress"])
            if dist < 0.18:
                influence = math.exp(-(dist * dist) / (2 * 0.055 * 0.055))
                y_offset += op["y_offset"] * influence
        current_y = actual_start_y + base_arc + y_offset + random.uniform(-5, 5)
        await page.mouse.move(target_x, current_y)

        bell = math.sin(math.pi * progress)
        delay_weight = 1 - bell * 0.45
        delay = (step_delay_min + random.random() * (step_delay_max - step_delay_min)) * delay_weight
        await page.wait_for_timeout(delay)
        last_x = target_x

    await page.wait_for_timeout(40 + random.random() * 80)
    overshoot = 5 + random.random() * 12
    await page.mouse.move(
        actual_start_x + distance + overshoot,
        actual_start_y + random.uniform(-25, 25),
        steps=2,
    )
    await page.wait_for_timeout(50 + random.random() * 90)
    await page.mouse.move(
        actual_start_x + distance,
        actual_start_y + random.uniform(-18, 18),
        steps=2,
    )
    await page.wait_for_timeout(60 + random.random() * 90)
    await page.mouse.up()


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
    screenshot_dir = os.path.join(os.getcwd(), "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    # 监听 Baxia 校验响应，辅助判定成功（不依赖 DOM）
    net_success = {"flag": False}

    def _on_response(resp) -> None:
        try:
            u = resp.url or ""
            if any(k in u for k in ("_____tmd_____", "x5sec", "baxia", "punish", "nc_captcha", "captcha")):
                # 2xx 且非 punish 页面可能表示通过
                if resp.status == 200 and "punish" not in u and "deny" not in u.lower():
                    # 延迟读 body 可能失败，仅作弱信号
                    pass
            # 消息 token 成功也算环境恢复信号
            if "idlemessage" in u and "token" in u and resp.status == 200 and "punish" not in u:
                net_success["flag"] = True
        except Exception:
            pass

    try:
        page.on("response", _on_response)
    except Exception:
        pass

    # 根据目标 URL 类型选择导航策略：
    # - punish URL（搜索上下文）：直接 goto punish URL，触发搜索场景的滑块
    # - 其他 URL（消息页上下文）：拟人路径进入 /im，避免直接 /im 触发反爬
    # _navigate_to_target 返回 (page, actual_url)，actual_url 供后续 navigate_fresh 刷新复用
    page, actual_im_url = await _navigate_to_target(page, target_url or DEFAULT_TARGET_URL)
    try:
        page.on("response", _on_response)
    except Exception:
        pass
    log(f"当前操作页 URL: {page.url}")
    log(f"✓ 记录目标页 URL（后续刷新复用）: {actual_im_url}")

    if await page_shows_load_failure(page):
        log("⚠ 进入消息页即出现「加载失败」——浏览器环境很可能已被风控标记")
        shot = os.path.join(screenshot_dir, f"load-fail-entry-{int(time.time())}.png")
        try:
            await page.screenshot(path=shot, full_page=False)
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
    MAX_HUMAN_ACTIONS = 2
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
                await page.screenshot(path=shot, full_page=False)
                last_screenshot = shot
                result["screenshotPath"] = shot
            except Exception:
                pass
            # 加载失败：硬重置（清 storage），用真人点击重新进入消息页
            page, actual_im_url = await navigate_fresh(page, actual_im_url, hard=True)
            if load_fail_streak >= 3:
                result["error"] = (
                    "连续出现「加载失败」：自动化浏览器环境被闲鱼风控标记，"
                    "即使人工拖拽也难以通过。请换用本机日常 Chrome 配置/新 Cookie 后重试"
                )
                return result
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

        if not detected and not has_punish:
            if await check_solved(page):
                log("✓ 未检测到滑块，验证通过！")
                result.update({"ok": True, "solved": True, "captchaDetected": False})
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
            return result

        if not slider_info:
            last_error = "未找到滑块按钮"
            log(last_error)
            shot = os.path.join(screenshot_dir, f"slider-not-found-{int(time.time())}.png")
            try:
                await page.screenshot(path=shot, full_page=False)
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
                return result

        pre_path = os.path.join(screenshot_dir, f"slider-pre-{attempt}-{int(time.time())}.png")
        try:
            await page.screenshot(path=pre_path, full_page=False)
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
            # 仅浏览器内 page.mouse（绝不控制系统鼠标）
            # 轮换：贝塞尔 / 元素悬停 / 微步 / 容器内 / 出容器
            mode = (attempt - 1) % 5
            if mode == 0:
                log(f"  attempt={attempt} 【贝塞尔】page.mouse")
                await bezier_mouse_drag(page, sx, sy, dist, attempt)
            elif mode == 1 and button_el is not None:
                log(f"  attempt={attempt} 【元素悬停】page.mouse")
                await element_hover_drag(page, button_el, dist, attempt)
            elif mode == 2:
                log(f"  attempt={attempt} 【微步】page.mouse")
                await microstep_drag(page, sx, sy, dist, attempt)
            elif mode == 3:
                log(f"  attempt={attempt} 【容器内】page.mouse")
                await human_like_drag(page, sx, sy, dist, attempt)
            else:
                log(f"  attempt={attempt} 【超出容器】page.mouse")
                await human_like_drag_out_of_container(page, sx, sy, dist, attempt)
        except Exception as e:
            last_error = f"拖动异常: {e}"
            log(last_error)
            page, actual_im_url = await navigate_fresh(page, actual_im_url, hard=False)
            continue

        result_wait = 2.6 + random.random() * 1.8
        log(f"等待 {result_wait:.1f} 秒验证结果...")
        await asyncio.sleep(result_wait)

        post_path = os.path.join(screenshot_dir, f"slider-post-{attempt}-{int(time.time())}.png")
        try:
            await page.screenshot(path=post_path, full_page=False)
            last_screenshot = post_path
            result["screenshotPath"] = post_path
        except Exception:
            pass

        solved = await check_solved(page)
        # 网络弱信号：token 接口 200 且无 punish
        if not solved and net_success.get("flag"):
            await asyncio.sleep(1.0)
            still = await detect_captcha_container(page)
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
            return result

        last_error = f"第 {attempt} 次拖动未通过"
        log(f"× {last_error}")

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
                except Exception:
                    pass
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
            # 自动处理 navigator.webdriver / window.chrome / userAgentData。
            # 关键：不注入 STEALTH_INIT_SCRIPT（会与 patchright 冲突，引入 toString 检测漏洞），
            #       不设置 user_agent（patchright 用真实 Chrome UA，手动覆盖会破坏一致性），
            #       不用 ignore_default_args（patchright 自动处理 --enable-automation）。
            # 只保留 patchright 不处理的高级指纹规避（WebGL/Canvas/Audio）。
            launch_kwargs = dict(
                user_data_dir=user_data_dir,
                headless=False,
                executable_path=chrome_path,
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
                    "--lang=zh-CN",
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
        if solve_result.get("solved"):
            fresh = await export_cookies(ctx)
            if fresh:
                solve_result["cookies"] = fresh
                solve_result["cookieCount"] = fresh.count("=")
                log(f"导出 {solve_result['cookieCount']} 个最新 cookies（{len(fresh)} 字符）")
            return solve_result

        # 全自动失败 → 半自动人工兜底（保留窗口供人工拖拽）
        if semi_auto_fallback and solve_result.get("captchaDetected") and not solve_result.get("isLoginPage"):
            log("全自动求解失败，尝试半自动人工兜底...")
            solve_result = await _semi_auto_human_fallback(ctx, solve_result, timeout_sec=120)
            if solve_result.get("solved"):
                return solve_result

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
        # 跨进程单飞：避免多账号同时求解把 IP/设备画像打爆
        with _FileLock(_SOLVE_LOCK_PATH, timeout=360.0):
            log("已获取全自动滑块全局锁")
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

                # 第二轮：仅当检测到滑块且未通过时，换 seed profile 再来一次
                # 第二轮不启用半自动兜底（第一轮已等过人工）
                # 搜索链路超时预算：前端 axios=180s，Java 网关→Python=180s，Python→crawler=180s，
                # crawler 内部 sliderSolver.ts 给 Python 脚本 90s，超时即 kill。
                # 第一轮 persistent profile 实测 60-90s，若已用时 > 75s，
                # 第二轮必然被 kill（且无法完整执行），跳过以保留第一轮结果与时间预算给后续兜底路径。
                elapsed_after_r1 = time.time() - start_time
                if (
                    not result.get("solved")
                    and result.get("captchaDetected")
                    and not result.get("isLoginPage")
                    and elapsed_after_r1 < 75.0
                ):
                    log("=== 第二轮：换 seed profile 重开浏览器再试 ===")
                    await asyncio.sleep(2.0 + random.random() * 2.5)
                    r2 = await _launch_solve_once(
                        p,
                        chrome_path,
                        ua,
                        cookie_str,
                        args.target_url,
                        max(2, min(3, int(args.max_retries or 3))),
                        proxy=proxy_cfg,
                        profile_strategy="seed",
                        semi_auto_fallback=False,
                    )
                    total_attempts += int(r2.get("attempts") or 0)
                    # 第二轮成功则覆盖；失败保留第一轮截图/错误
                    if r2.get("solved"):
                        result.update(r2)
                    else:
                        result["attempts"] = total_attempts
                        if r2.get("error"):
                            result["error"] = (
                                f"{result.get('error') or ''} | 第二轮: {r2.get('error')}"
                            ).strip(" |")
                        if r2.get("screenshotPath"):
                            result["screenshotPath"] = r2.get("screenshotPath")
                elif (
                    not result.get("solved")
                    and result.get("captchaDetected")
                    and not result.get("isLoginPage")
                ):
                    # 第二轮因 deadline 跳过：保留第一轮结果给上层
                    log(f"=== 第二轮跳过（elapsed={elapsed_after_r1:.1f}s >= 75s），保留第一轮结果 ===")
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
    args = parser.parse_args()
    result = asyncio.run(main_async(args))
    output_result(result)
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
