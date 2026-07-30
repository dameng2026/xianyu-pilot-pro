"""AI 客服自主学习调度器：每天扫描前台 nav.js 变化并录入知识库。

设计目标
========
项目几乎每天更新，前台新功能页面会不断加入。AI 客服（小梦）需要"自主学习"能力：
- 定时扫描 apps/user-web/src/data/nav.js 文件
- 解析其中所有 navCategories 与子项 items
- 与 ai_cs_knowledge 表中 category='系统功能' 的现有条目对比
- 新增的功能 → 写入 ai_cs_knowledge 表（tenant_id=NULL, enabled=1）
- 已存在的功能 → 跳过（避免重复）
- 已删除的功能 → 标记 enabled=0（保留历史，不真删）

调度策略
========
- 单实例运行：通过 _scheduler_started 标志防止重复启动；
- 异常容错：单次扫描异常不影响下一次；
- 优雅关闭：通过 _scheduler_stop_event 通知退出；
- 启动延迟：服务启动后 5 分钟开始首次扫描，避免与启动初始化竞争；
- 扫描间隔：24 小时（每天一次）；
- 维护窗口：扫描前先尝试触发 Java 端知识库索引重建接口。

与 list_system_features 工具的关系
================================
- list_system_features 工具读 SYSTEM_FEATURES 全局变量（内存）
- 本调度器在每次扫描成功后，同步更新 SYSTEM_FEATURES 全局变量
- 这样工具调用始终返回最新功能清单，无需重启服务
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 扫描间隔（秒）= 24 小时
SCAN_INTERVAL_SECONDS = 24 * 60 * 60

# 启动后延迟首次扫描（秒）= 5 分钟
INITIAL_DELAY_SECONDS = 5 * 60

# nav.js 文件路径（相对于项目根目录）
# 优先从环境变量读取，否则用相对路径
NAV_JS_FILENAME = "nav.js"
NAV_JS_SEARCH_PATHS = [
    # 项目根目录/apps/user-web/src/data/nav.js
    os.path.join("..", "..", "..", "apps", "user-web", "src", "data", NAV_JS_FILENAME),
    # 部署目录相对路径
    os.path.join("/home", "ubuntu", "project", "apps", "user-web", "src", "data", NAV_JS_FILENAME),
    # Windows 开发环境
    os.path.join("g:\\源码\\xianyu-assistant-package-temp", "apps", "user-web", "src", "data", NAV_JS_FILENAME),
]

# 调度器状态
_scheduler_task: Optional[asyncio.Task] = None
_scheduler_started: bool = False
_scheduler_stop_event: Optional[asyncio.Event] = None

# 最近一次扫描结果
_last_scan_result: Optional[dict] = None
_last_scan_at: Optional[datetime] = None


def _find_nav_js_file() -> Optional[str]:
    """查找 nav.js 文件路径。"""
    # 1. 从环境变量读取
    env_path = os.environ.get("USER_WEB_NAV_JS_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. 从当前工作目录尝试
    cwd = os.getcwd()
    for rel_path in NAV_JS_SEARCH_PATHS:
        abs_path = os.path.normpath(os.path.join(cwd, rel_path))
        if os.path.isfile(abs_path):
            return abs_path

    # 3. 向上递归查找 apps/user-web/src/data/nav.js
    cur = cwd
    for _ in range(10):
        candidate = os.path.join(cur, "apps", "user-web", "src", "data", NAV_JS_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    return None


def _parse_nav_js(content: str) -> List[Dict[str, Any]]:
    """解析 nav.js 文件内容，提取 navCategories 数组。

    nav.js 格式示例：
        export const navCategories = [
          {
            key: 'overview',
            title: '概览',
            icon: 'overview',
            items: [
              { key: 'dashboard', label: '导航面板', icon: 'dashboard' },
              ...
            ]
          },
          ...
        ]

    解析策略：使用正则提取 key/title/label 字段，避免引入 JS 解析依赖。
    """
    features: List[Dict[str, Any]] = []
    try:
        # 找到 navCategories = [ ... ] 块
        match = re.search(r"navCategories\s*=\s*\[", content)
        if not match:
            logger.warning("nav.js 中未找到 navCategories 数组")
            return features

        start = match.end() - 1  # 指向 [
        # 找到匹配的 ]
        depth = 0
        end = -1
        for i in range(start, len(content)):
            ch = content[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end < 0:
            logger.warning("nav.js navCategories 数组未闭合")
            return features

        block = content[start + 1:end]

        # 按一级分类拆分（每个一级分类以 { key: 'xxx', title: 'xxx' 开头）
        # 简单策略：用 "key: '" 分割
        cat_pattern = re.compile(
            r"key:\s*['\"]([^'\"]+)['\"]\s*,\s*title:\s*['\"]([^'\"]+)['\"]",
            re.MULTILINE,
        )
        # 找到所有一级分类的位置
        cat_matches = list(cat_pattern.finditer(block))
        for idx, cat_match in enumerate(cat_matches):
            cat_key = cat_match.group(1)
            cat_title = cat_match.group(2)
            # 截取该分类的 items 块（直到下一个分类或块结束）
            block_start = cat_match.end()
            block_end = cat_matches[idx + 1].start() if idx + 1 < len(cat_matches) else len(block)
            cat_block = block[block_start:block_end]

            # 提取 items 数组中的 { key: 'xxx', label: 'xxx' } 项
            item_pattern = re.compile(
                r"\{\s*key:\s*['\"]([^'\"]+)['\"]\s*,\s*label:\s*['\"]([^'\"]+)['\"]"
                r"(?:[^}]*?maintenance:\s*(true|false))?",
            )
            cat_features: List[Dict[str, Any]] = []
            for item_match in item_pattern.finditer(cat_block):
                item_key = item_match.group(1)
                item_label = item_match.group(2)
                is_maintenance = item_match.group(3) == "true"
                cat_features.append({
                    "key": item_key,
                    "name": item_label,
                    "maintenance": is_maintenance,
                    "category": cat_title,
                    "categoryKey": cat_key,
                })
            if cat_features:
                features.append({
                    "category": cat_title,
                    "categoryKey": cat_key,
                    "features": cat_features,
                })
    except Exception as exc:
        logger.warning("解析 nav.js 失败 errorType=%s err=%s", type(exc).__name__, exc, exc_info=True)
    return features


async def _fetch_existing_kb_features(db: AsyncSession) -> Dict[str, Dict[str, Any]]:
    """查询 ai_cs_knowledge 表中 category='系统功能' 的现有条目。

    返回 {title: row_dict} 字典，title 为功能 key（如 "products"）。
    """
    try:
        rows = (await db.execute(text("""
            SELECT id, title, content, keywords, enabled
            FROM ai_cs_knowledge
            WHERE category = '系统功能'
              AND (tenant_id IS NULL OR tenant_id = 0)
            ORDER BY id ASC
        """))).mappings().all()
        result: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            title = (row.get("title") or "").strip()
            if title:
                result[title] = dict(row)
        return result
    except Exception as exc:
        logger.warning("查询 ai_cs_knowledge 系统功能条目失败 errorType=%s", type(exc).__name__, exc_info=True)
        return {}


def _build_feature_content(cat_title: str, feat: Dict[str, Any]) -> str:
    """根据功能项构建知识库内容文本。"""
    name = feat.get("name", "")
    key = feat.get("key", "")
    is_maintenance = feat.get("maintenance", False)
    maintenance_note = "（当前为维护中状态，暂不可用）" if is_maintenance else ""
    return (
        f"功能名称：{name}{maintenance_note}\n"
        f"所属分类：{cat_title}\n"
        f"路由 key：{key}\n"
        f"说明：用户可通过左侧导航栏「{cat_title}」分类下的「{name}」入口访问此功能。"
    )


async def _sync_features_to_kb(db: AsyncSession, features: List[Dict[str, Any]]) -> Dict[str, int]:
    """将功能清单同步到 ai_cs_knowledge 表。

    返回 {"added": N, "updated": N, "disabled": N} 统计。
    """
    existing = await _fetch_existing_kb_features(db)

    # 当前功能 key 集合（用于后续禁用已删除功能）
    current_keys: set = set()
    added = 0
    updated = 0

    for cat in features:
        cat_title = cat.get("category", "")
        for feat in cat.get("features", []):
            feat_key = feat.get("key", "")
            if not feat_key:
                continue
            current_keys.add(feat_key)
            content = _build_feature_content(cat_title, feat)
            keywords = f"{cat_title},{feat.get('name', '')},{feat_key}"
            existing_row = existing.get(feat_key)
            if existing_row is None:
                # 新增
                try:
                    await db.execute(text("""
                        INSERT INTO ai_cs_knowledge
                            (tenant_id, category, title, content, keywords,
                             priority, sort_order, enabled, created_time, updated_time)
                        VALUES
                            (NULL, '系统功能', :title, :content, :keywords,
                             90, 0, 1, NOW(), NOW())
                    """), {
                        "title": feat_key,
                        "content": content,
                        "keywords": keywords,
                    })
                    added += 1
                except Exception as exc:
                    logger.warning("新增系统功能知识库条目失败 key=%s errorType=%s", feat_key, type(exc).__name__, exc_info=True)
            else:
                # 已存在，检查内容是否需要更新
                if (existing_row.get("content") or "") != content:
                    try:
                        await db.execute(text("""
                            UPDATE ai_cs_knowledge
                            SET content = :content, keywords = :keywords,
                                enabled = 1, updated_time = NOW()
                            WHERE id = :id
                        """), {
                            "content": content,
                            "keywords": keywords,
                            "id": existing_row.get("id"),
                        })
                        updated += 1
                    except Exception as exc:
                        logger.warning("更新系统功能知识库条目失败 key=%s errorType=%s", feat_key, type(exc).__name__, exc_info=True)
                elif not existing_row.get("enabled"):
                    # 内容相同但被禁用了，重新启用
                    try:
                        await db.execute(text("""
                            UPDATE ai_cs_knowledge SET enabled = 1, updated_time = NOW() WHERE id = :id
                        """), {"id": existing_row.get("id")})
                        updated += 1
                    except Exception:
                        pass

    # 禁用已删除的功能（在 existing 中但不在 current_keys 中）
    disabled = 0
    for title, row in existing.items():
        if title not in current_keys and row.get("enabled"):
            try:
                await db.execute(text("""
                    UPDATE ai_cs_knowledge SET enabled = 0, updated_time = NOW() WHERE id = :id
                """), {"id": row.get("id")})
                disabled += 1
            except Exception as exc:
                logger.warning("禁用过期系统功能条目失败 title=%s errorType=%s", title, type(exc).__name__, exc_info=True)

    try:
        await db.commit()
    except Exception as exc:
        logger.warning("提交系统功能知识库同步失败 errorType=%s", type(exc).__name__, exc_info=True)
        await db.rollback()
        return {"added": 0, "updated": 0, "disabled": 0, "error": str(exc)}

    return {"added": added, "updated": updated, "disabled": disabled}


async def _trigger_kb_index_rebuild() -> bool:
    """触发 Java 端知识库索引重建（让 RAG 检索能查询到新功能）。

    通过 HTTP 调用 Java 端 /api/ai-cs/knowledge/rebuild 接口。
    失败不影响主流程，仅记录日志。
    """
    try:
        import httpx
        from ..core.config import settings
        base_url = getattr(settings, "core_api_base_url", None) or "http://localhost:18080"
        # 与 ai_cs_runtime.py 保持一致：使用 effective_internal_api_token，避免读到空 token 触发 401
        internal_token = getattr(settings, "effective_internal_api_token", "") or ""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{base_url}/api/ai-cs/knowledge/rebuild",
                headers={"X-Internal-Token": internal_token},
            )
            if resp.status_code == 200:
                logger.info("AI 客服知识库索引重建已触发")
                return True
            logger.warning("AI 客服知识库索引重建失败 status=%d", resp.status_code)
            return False
    except Exception as exc:
        logger.debug("触发知识库索引重建异常 errorType=%s", type(exc).__name__)
        return False


async def _update_system_features_runtime(features: List[Dict[str, Any]]) -> None:
    """同步更新 ai_cs_tools.SYSTEM_FEATURES 全局变量（运行时热加载）。

    这样 list_system_features 工具调用始终返回最新功能清单，无需重启服务。
    """
    try:
        from . import ai_cs_tools
        # 转换格式：保留 category + features，但 features 字段精简
        runtime_features: List[Dict[str, Any]] = []
        for cat in features:
            cat_title = cat.get("category", "")
            cat_features = []
            for feat in cat.get("features", []):
                maintenance = feat.get("maintenance", False)
                cat_features.append({
                    "key": feat.get("key", ""),
                    "name": feat.get("name", ""),
                    "desc": f"{feat.get('name', '')}（{cat_title}分类下）" + ("（维护中）" if maintenance else ""),
                })
            if cat_features:
                runtime_features.append({
                    "category": cat_title,
                    "features": cat_features,
                })
        if runtime_features:
            ai_cs_tools.SYSTEM_FEATURES = runtime_features
            logger.info("SYSTEM_FEATURES 运行时已热更新，共 %d 个分类", len(runtime_features))
    except Exception as exc:
        logger.warning("更新 SYSTEM_FEATURES 运行时变量失败 errorType=%s", type(exc).__name__, exc_info=True)


async def scan_and_sync_features(db_factory=None) -> Dict[str, Any]:
    """扫描 nav.js 并同步到知识库。

    参数：
    - db_factory: 可选的异步上下文管理器工厂，用于创建 db session。
                  不传则使用项目默认的 AsyncSessionLocal。

    返回同步结果字典。
    """
    global _last_scan_result, _last_scan_at

    scan_start = datetime.now()
    result: Dict[str, Any] = {
        "scanned_at": scan_start.isoformat(),
        "nav_js_path": None,
        "categories_count": 0,
        "features_count": 0,
        "added": 0,
        "updated": 0,
        "disabled": 0,
        "error": None,
    }

    # 1. 查找 nav.js 文件
    nav_path = _find_nav_js_file()
    if not nav_path:
        result["error"] = "nav.js 文件未找到"
        logger.warning("AI 客服自主学习扫描跳过：nav.js 文件未找到")
        _last_scan_result = result
        _last_scan_at = scan_start
        return result
    result["nav_js_path"] = nav_path

    # 2. 读取并解析 nav.js
    try:
        with open(nav_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        result["error"] = f"读取 nav.js 失败：{exc}"
        logger.warning("AI 客服自主学习读取 nav.js 失败 errorType=%s", type(exc).__name__, exc_info=True)
        _last_scan_result = result
        _last_scan_at = scan_start
        return result

    features = _parse_nav_js(content)
    if not features:
        result["error"] = "nav.js 解析后未得到任何功能项"
        logger.warning("AI 客服自主学习：nav.js 解析后功能清单为空")
        _last_scan_result = result
        _last_scan_at = scan_start
        return result

    result["categories_count"] = len(features)
    result["features_count"] = sum(len(c.get("features", [])) for c in features)

    # 3. 更新运行时 SYSTEM_FEATURES（无论数据库是否成功，先热加载到内存）
    await _update_system_features_runtime(features)

    # 4. 同步到 ai_cs_knowledge 表
    try:
        if db_factory is not None:
            async with db_factory() as db:
                sync_result = await _sync_features_to_kb(db, features)
        else:
            # 与 app/core/database.py 中的会话工厂保持一致：async_session（非 AsyncSessionLocal）
            from ..core.database import async_session
            async with async_session() as db:
                sync_result = await _sync_features_to_kb(db, features)
        result.update(sync_result)
    except Exception as exc:
        result["error"] = f"同步知识库失败：{exc}"
        logger.warning("AI 客服自主学习同步知识库失败 errorType=%s", type(exc).__name__, exc_info=True)

    # 5. 触发知识库索引重建
    await _trigger_kb_index_rebuild()

    logger.info(
        "AI 客服自主学习扫描完成: categories=%d features=%d added=%d updated=%d disabled=%d",
        result["categories_count"], result["features_count"],
        result.get("added", 0), result.get("updated", 0), result.get("disabled", 0),
    )

    _last_scan_result = result
    _last_scan_at = scan_start
    return result


async def _scheduler_loop() -> None:
    """调度器主循环。"""
    logger.info(
        "AI 客服自主学习调度器启动，首次扫描将在 %d 秒后开始，间隔 %d 秒",
        INITIAL_DELAY_SECONDS, SCAN_INTERVAL_SECONDS,
    )

    # 启动延迟
    try:
        await asyncio.wait_for(_scheduler_stop_event.wait(), timeout=INITIAL_DELAY_SECONDS)
        logger.info("AI 客服自主学习调度器在启动延迟期收到停止信号，退出")
        return
    except asyncio.TimeoutError:
        pass

    while not _scheduler_stop_event.is_set():
        try:
            await scan_and_sync_features()
        except Exception as e:
            logger.exception("AI 客服自主学习调度器扫描异常: %s", e)

        # 等待下一次扫描
        try:
            await asyncio.wait_for(_scheduler_stop_event.wait(), timeout=SCAN_INTERVAL_SECONDS)
            break
        except asyncio.TimeoutError:
            continue

    logger.info("AI 客服自主学习调度器已退出")


async def start_feature_sync_scheduler() -> None:
    """启动 AI 客服自主学习调度器（幂等）。"""
    global _scheduler_task, _scheduler_started, _scheduler_stop_event

    if _scheduler_started and _scheduler_task and not _scheduler_task.done():
        logger.info("AI 客服自主学习调度器已在运行，跳过重复启动")
        return

    _scheduler_stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="ai_cs_feature_sync_scheduler")
    _scheduler_started = True
    logger.info("AI 客服自主学习调度器已注册")


async def stop_feature_sync_scheduler() -> None:
    """停止 AI 客服自主学习调度器（幂等）。"""
    global _scheduler_task, _scheduler_started, _scheduler_stop_event

    if not _scheduler_started:
        return

    if _scheduler_stop_event:
        _scheduler_stop_event.set()

    if _scheduler_task and not _scheduler_task.done():
        try:
            await asyncio.wait_for(_scheduler_task, timeout=10)
        except asyncio.TimeoutError:
            _scheduler_task.cancel()
            try:
                await _scheduler_task
            except (asyncio.CancelledError, Exception):
                pass

    _scheduler_started = False
    _scheduler_task = None
    _scheduler_stop_event = None
    logger.info("AI 客服自主学习调度器已停止")


def get_scheduler_status() -> dict:
    """获取调度器状态（供诊断接口使用）。"""
    return {
        "started": _scheduler_started,
        "running": bool(_scheduler_task and not _scheduler_task.done()),
        "last_scan_at": _last_scan_at.isoformat() if _last_scan_at else None,
        "last_scan_result": _last_scan_result,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
    }
