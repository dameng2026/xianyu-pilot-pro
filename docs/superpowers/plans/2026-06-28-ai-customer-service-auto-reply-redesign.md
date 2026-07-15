# AI 客服 & 自动回复功能重构 - 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重构 AI 客服配置页面（文件上传/大段文本/恢复默认/预览修复）、自动回复页面（双列+极简面板）、商品管理页面（直接开关+前置校验），建立商品级>账号级>全局的三档作用域启用机制。

**Architecture:** Python 提供 `knowledge_base.py`（文件解析+AI提取）和 `auto_reply_scope.py`（作用域 CRUD）两个新路由；Java 网关新增 `AutoReplyScopeController` 透传，扩展 `BusinessSettingsController` 支持默认值与文件上传代理；前端三个页面按设计文档改造。复用 `AutomationClient.uploadInternalForData` 处理 multipart 透传。

**Tech Stack:** Python(FastAPI+SQLAlchemy+python-pptx+openpyxl) / Java(Spring Boot+JdbcTemplate) / Vue 3(Composition API)

**关联设计文档:** `docs/superpowers/specs/2026-06-28-ai-customer-service-auto-reply-redesign.md`

---

## 文件结构总览

### 新建文件
| 文件 | 职责 |
|------|------|
| `apps/automation-service/app/api/v1/routes/knowledge_base.py` | 文件解析（MD/PPT/Excel）+ AI 提取规则 |
| `apps/automation-service/app/api/v1/routes/auto_reply_scope.py` | 商品/账号级 enabled 状态 CRUD |
| `apps/core-api/src/main/java/com/xianyu/admin/controller/AutoReplyScopeController.java` | Java 网关透传作用域接口 |
| `apps/user-web/src/api/autoReplyScope.js` | 前端作用域 API 封装 |

### 修改文件
| 文件 | 改动 |
|------|------|
| `apps/automation-service/app/models/entities.py` | `XianyuGoods` 新增 `auto_reply_enabled` 列 |
| `apps/automation-service/app/api/v1/api.py` | 注册两个新路由 |
| `apps/automation-service/app/api/v1/routes/items.py` | 替换 `updateAutoReplyStatus` 占位实现 |
| `apps/automation-service/requirements.txt` | 新增 `python-pptx` 依赖 |
| `apps/core-api/.../service/BusinessSettingsService.java` | 优化默认值 + 新增 `getDefaults()` |
| `apps/core-api/.../controller/BusinessSettingsController.java` | 新增 `/defaults` 和 `/upload-knowledge` |
| `apps/user-web/src/api/businessSettings.js` | 新增 `getAiCsDefaults` 和 `uploadKnowledgeBase` |
| `apps/user-web/src/pages/settings/AiCsSettings.vue` | 文件上传+大段文本+恢复默认+预览修复 |
| `apps/user-web/src/pages/ProductsPage.vue` | 自动回复开关直接生效+前置校验+批量 |
| `apps/user-web/src/pages/AutoReplyPage.vue` | 双列重构+极简策略面板 |

---

## Phase 1: 数据库与实体层

### Task 1: 数据库迁移 - xianyu_goods 新增 auto_reply_enabled 列

**Files:**
- Modify: `apps/automation-service/app/models/entities.py` (XianyuGoods 类，约第 89-115 行)

- [ ] **Step 1: 在 XianyuGoods 实体类新增 auto_reply_enabled 列**

编辑 `apps/automation-service/app/models/entities.py`，在 `XianyuGoods` 类的 `deleted` 字段之后（约第 113 行后）新增：

```python
    auto_reply_enabled = Column(SmallInteger, nullable=True, default=None, comment="NULL继承账号级/全局 0强制关 1强制开")
```

- [ ] **Step 2: 手动执行数据库 ALTER TABLE**

运行 SQL（在项目数据库中执行）：

```sql
ALTER TABLE xianyu_goods 
  ADD COLUMN auto_reply_enabled TINYINT NULL DEFAULT NULL 
  COMMENT 'NULL继承账号级/全局 0强制关 1强制开';
```

- [ ] **Step 3: 验证列已添加**

运行: 在数据库客户端执行 `DESCRIBE xianyu_goods;` 或 `PRAGMA table_info(xianyu_goods);`
Expected: 列表中包含 `auto_reply_enabled` 字段

- [ ] **Step 4: Commit**

```bash
git add apps/automation-service/app/models/entities.py
git commit -m "feat(db): 在 xianyu_goods 表新增 auto_reply_enabled 列支持商品级自动回复开关"
```

---

## Phase 2: Python 后端 - 知识库提取路由

### Task 2: 新建 knowledge_base.py 路由 - 文件解析与 AI 提取

**Files:**
- Create: `apps/automation-service/app/api/v1/routes/knowledge_base.py`

- [ ] **Step 1: 创建 knowledge_base.py 文件**

写入以下完整内容：

```python
"""
知识库文件上传与 AI 规则提取路由。
支持 .md / .ppt / .pptx / .xlsx / .xls / .csv 文件，
由 AI 模型自动提取客服回复规则，返回结构化 Markdown 文本。
"""
import io
import csv
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_internal_token
from app.core.response import ResultObject
from app.services.ai_provider_service import ai_provider_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-base", tags=["knowledgeBase"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".md", ".txt", ".ppt", ".pptx", ".xlsx", ".xls", ".csv"}

EXTRACT_PROMPT_TEMPLATE = """你是客服规则提取助手。请从以下文件内容中提取所有可作为 AI 客服回复规则的信息，输出为结构化 Markdown 文本。

要求：
1. 按类别分组，使用二级标题（如 ## 售后政策 / ## 发货说明 / ## 商品 FAQ / ## 退换货规则 / ## 价格优惠 / ## 规格参数）
2. 每条规则用 "- " 开头，包含：触发场景、回复要点、注意事项
3. 只输出与客服回复相关的内容，忽略文件中的导航、版权、广告等无关信息
4. 保持原文事实，不要编造规则
5. 如果文件内容与客服无关，返回空字符串

文件内容：
{file_content}
"""


@router.post("/extract")
async def extract_knowledge_base(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """接收文件，解析后调用 AI 提取客服回复规则，返回结构化 Markdown。"""
    try:
        filename = file.filename or "unknown"
        ext = _get_extension(filename)
        if ext not in ALLOWED_EXTENSIONS:
            return ResultObject.fail(f"不支持的文件格式：{ext}，仅支持 {', '.join(sorted(ALLOWED_EXTENSIONS))}")

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            return ResultObject.fail(f"文件不能超过 10MB（当前 {len(content) / 1024 / 1024:.1f}MB）")

        file_text = _parse_file(ext, content, filename)
        if not file_text.strip():
            return ResultObject.fail("文件内容为空或无法解析")

        # 截断过长的文件内容，避免超出 AI 模型上下文限制
        if len(file_text) > 30000:
            file_text = file_text[:30000] + "\n\n（文件内容过长，已截断）"
            logger.info("文件 %s 内容截断至 30000 字符", filename)

        prompt = EXTRACT_PROMPT_TEMPLATE.format(file_content=file_text)
        extracted = await ai_provider_service.generate_text_async(
            scene="knowledge_base_extract",
            system_prompt="你是专业的客服规则提取助手，擅长从文档中提炼结构化的客服回复规则。",
            user_prompt=prompt,
            temperature=0.3,
        )

        if not extracted or not extracted.strip():
            return ResultObject.fail("AI 未能从文件中提取有效规则，请检查文件内容或重试")

        rule_count = extracted.count("\n- ") + (1 if extracted.strip().startswith("- ") else 0)
        return ResultObject.success({
            "extractedText": extracted.strip(),
            "ruleCount": max(rule_count, 0),
            "fileName": filename,
        })
    except Exception as e:
        logger.exception("知识库文件提取失败 filename=%s", filename)
        return ResultObject.fail(f"文件处理失败：{e}")


def _get_extension(filename: str) -> str:
    """获取文件扩展名（小写，带点）。"""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _parse_file(ext: str, content: bytes, filename: str) -> str:
    """根据扩展名选择解析器，提取纯文本。"""
    try:
        if ext in (".md", ".txt"):
            return content.decode("utf-8", errors="ignore")
        if ext in (".csv",):
            return _parse_csv(content)
        if ext in (".xlsx", ".xls"):
            return _parse_excel(content)
        if ext in (".ppt", ".pptx"):
            return _parse_ppt(content)
        return content.decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning("文件 %s 解析失败 ext=%s err=%s", filename, ext, e)
        raise RuntimeError(f"文件解析失败：{e}")


def _parse_csv(content: bytes) -> str:
    """解析 CSV 文件，返回表格文本。"""
    text = content.decode("utf-8-sig", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    lines = []
    for row in reader:
        if any(cell.strip() for cell in row):
            lines.append(" | ".join(row))
    return "\n".join(lines)


def _parse_excel(content: bytes) -> str:
    """解析 Excel 文件，返回所有 sheet 的表格文本。"""
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(content), data_only=True)
    lines = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        lines.append(f"### 工作表：{sheet_name}")
        for row in ws.iter_rows(values_only=True):
            if any(cell is not None and str(cell).strip() for cell in row):
                lines.append(" | ".join(str(cell) if cell is not None else "" for cell in row))
        lines.append("")
    return "\n".join(lines)


def _parse_ppt(content: bytes) -> str:
    """解析 PPT 文件，返回所有幻灯片文本。"""
    from pptx import Presentation
    prs = Presentation(io.BytesIO(content))
    lines = []
    for idx, slide in enumerate(prs.slides, start=1):
        slide_texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        slide_texts.append(text)
            if shape.has_table:
                for row in shape.table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells)
                    if row_text.strip(" |"):
                        slide_texts.append(row_text)
        if slide_texts:
            lines.append(f"### 幻灯片 {idx}")
            lines.extend(slide_texts)
            lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 2: 检查 ai_provider_service 是否有 generate_text_async 方法**

运行: `grep -rn "generate_text_async\|async def generate_text" apps/automation-service/app/services/ai_provider_service.py`
Expected: 找到异步生成方法。如果没有，需要新增（见下一步）。

- [ ] **Step 3: 如缺少异步方法，在 ai_provider_service 新增 generate_text_async**

编辑 `apps/automation-service/app/services/ai_provider_service.py`，新增异步方法（如已有则跳过）。参考现有同步方法的实现，用 `asyncio.to_thread` 包装：

```python
import asyncio

async def generate_text_async(self, scene: str, system_prompt: str, user_prompt: str, temperature: float = 0.6) -> str:
    """异步调用 AI 生成文本，避免阻塞事件循环。"""
    return await asyncio.to_thread(
        self.generate_text_sync, scene, system_prompt, user_prompt, temperature
    )
```

注意：实际方法名和签名需根据现有 `ai_provider_service.py` 调整。如果现有方法是同步的 `generate_text`，则改为：
```python
async def generate_text_async(self, scene, system_prompt, user_prompt, temperature=0.6):
    return await asyncio.to_thread(self.generate_text, scene, system_prompt, user_prompt, temperature)
```

- [ ] **Step 4: 在 api.py 注册 knowledge_base 路由**

编辑 `apps/automation-service/app/api/v1/api.py`，在第 9 行 `from .routes import restful as restful_module` 后新增：

```python
from .routes import knowledge_base as knowledge_base_module
```

在 `api_router.include_router(restful_module.router, tags=['restful'])` 后新增（约第 48 行后）：

```python
api_router.include_router(knowledge_base_module.router, tags=['knowledgeBase'])
```

- [ ] **Step 5: 安装 Python 依赖**

运行:
```bash
cd apps/automation-service
pip install python-pptx openpyxl
```

检查 `requirements.txt` 是否已包含 `openpyxl`，如无则添加。在 `apps/automation-service/requirements.txt` 末尾新增（如尚不存在）：
```
python-pptx>=0.6.21
openpyxl>=3.1.0
```

- [ ] **Step 6: 启动服务验证路由注册**

运行: 重启 automation-service，访问 `http://localhost:12401/docs`，查找 `/api/knowledge-base/extract` 端点
Expected: 在 Swagger 文档中看到 `/api/knowledge-base/extract` POST 端点

- [ ] **Step 7: Commit**

```bash
git add apps/automation-service/app/api/v1/routes/knowledge_base.py apps/automation-service/app/api/v1/api.py apps/automation-service/requirements.txt
git commit -m "feat(python): 新增知识库文件上传与 AI 规则提取路由"
```

---

## Phase 3: Python 后端 - 作用域管理路由

### Task 3: 新建 auto_reply_scope.py 路由 - 商品/账号级 enabled 管理

**Files:**
- Create: `apps/automation-service/app/api/v1/routes/auto_reply_scope.py`

- [ ] **Step 1: 创建 auto_reply_scope.py 文件**

写入以下完整内容：

```python
"""
自动回复作用域管理路由。
支持三档作用域：
- 全局：ai-customer-service.enabled（主开关，在 BusinessSettingsService 管理）
- 账号级：user_business_setting 的 auto-reply-account-scopes 配置
- 商品级：xianyu_goods.auto_reply_enabled 列

作用域优先级：商品级 > 账号级 > 全局（NULL 不继承全局，默认关闭）。
"""
import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import verify_internal_token
from app.core.response import ResultObject
from app.models.entities import XianyuGoods
from app.core.tenant_context import get_current_tenant_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auto-reply-scope", tags=["autoReplyScope"])

ACCOUNT_SCOPES_KEY = "auto-reply-account-scopes"


@router.get("/products")
async def list_products_with_scope(
    accountId: Optional[int] = Query(None, description="账号ID，不传则返回全部账号商品"),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """返回商品列表及每个商品的 effective auto_reply 状态。"""
    try:
        tenant_id = get_current_tenant_id()
        stmt = select(XianyuGoods).where(
            XianyuGoods.tenant_id == tenant_id,
            XianyuGoods.deleted == 0,
        )
        if accountId is not None:
            stmt = stmt.where(XianyuGoods.account_id == accountId)
        stmt = stmt.order_by(XianyuGoods.created_time.desc())
        result = await db.execute(stmt)
        goods_list = result.scalars().all()

        account_scopes = await _load_account_scopes(db, tenant_id)
        global_enabled = await _load_global_enabled(db, tenant_id)

        items = []
        for g in goods_list:
            effective = _compute_effective(g.auto_reply_enabled, g.account_id, account_scopes, global_enabled)
            items.append({
                "id": g.id,
                "title": g.title or "",
                "accountId": g.account_id,
                "goodsId": g.external_goods_id,
                "auto_reply_enabled": g.auto_reply_enabled,
                "effective_enabled": effective,
                "account_enabled": account_scopes.get("accounts", {}).get(str(g.account_id)) if account_scopes else None,
                "global_enabled": global_enabled,
            })
        return ResultObject.success({"items": items, "total": len(items)})
    except Exception as e:
        logger.exception("查询商品作用域列表失败")
        return ResultObject.fail(f"查询失败：{e}")


@router.post("/product")
async def update_product_scope(
    req: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """更新单个商品的 auto_reply_enabled。"""
    try:
        item_id = req.get("itemId")
        enabled = req.get("enabled")
        if item_id is None or enabled is None:
            return ResultObject.fail("缺少 itemId 或 enabled 参数")
        tenant_id = get_current_tenant_id()
        value = 1 if bool(enabled) else 0
        stmt = update(XianyuGoods).where(
            XianyuGoods.id == int(item_id),
            XianyuGoods.tenant_id == tenant_id,
        ).values(auto_reply_enabled=value)
        result = await db.execute(stmt)
        await db.commit()
        if result.rowcount == 0:
            return ResultObject.fail("商品不存在或无权操作")
        logger.info("更新商品 auto_reply_enabled itemId=%s enabled=%s", item_id, value)
        return ResultObject.success({"ok": True, "itemId": int(item_id), "enabled": bool(enabled)})
    except Exception as e:
        logger.exception("更新商品作用域失败 itemId=%s", req.get("itemId"))
        return ResultObject.fail(f"更新失败：{e}")


@router.post("/account")
async def update_account_scope(
    req: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """更新账号级 auto_reply 启用状态（存储在 user_business_setting 的 auto-reply-account-scopes 配置中）。"""
    try:
        account_id = req.get("accountId")
        enabled = req.get("enabled")
        if account_id is None or enabled is None:
            return ResultObject.fail("缺少 accountId 或 enabled 参数")
        tenant_id = get_current_tenant_id()
        scopes = await _load_account_scopes(db, tenant_id)
        accounts = scopes.setdefault("accounts", {})
        accounts[str(int(account_id))] = bool(enabled)
        await _save_account_scopes(db, tenant_id, scopes)
        logger.info("更新账号作用域 accountId=%s enabled=%s", account_id, enabled)
        return ResultObject.success({"ok": True, "accountId": int(account_id), "enabled": bool(enabled)})
    except Exception as e:
        logger.exception("更新账号作用域失败 accountId=%s", req.get("accountId"))
        return ResultObject.fail(f"更新失败：{e}")


@router.post("/batch")
async def batch_update_scope(
    req: Dict[str, Any] = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """批量更新商品或账号的 auto_reply 状态。

    Body:
      - {"itemIds": [1,2,3], "enabled": true}  批量更新商品
      - {"accountIds": [1,2], "enabled": true}  批量更新账号
    """
    try:
        tenant_id = get_current_tenant_id()
        enabled = req.get("enabled")
        if enabled is None:
            return ResultObject.fail("缺少 enabled 参数")
        value = bool(enabled)

        item_ids = req.get("itemIds")
        account_ids = req.get("accountIds")

        if item_ids:
            int_ids = [int(i) for i in item_ids if i is not None]
            if int_ids:
                stmt = update(XianyuGoods).where(
                    XianyuGoods.id.in_(int_ids),
                    XianyuGoods.tenant_id == tenant_id,
                ).values(auto_reply_enabled=1 if value else 0)
                result = await db.execute(stmt)
                await db.commit()
                logger.info("批量更新商品 auto_reply affected=%s enabled=%s", result.rowcount, value)
                return ResultObject.success({"ok": True, "affected": result.rowcount, "type": "product"})

        if account_ids:
            int_ids = [int(i) for i in account_ids if i is not None]
            if int_ids:
                scopes = await _load_account_scopes(db, tenant_id)
                accounts = scopes.setdefault("accounts", {})
                for aid in int_ids:
                    accounts[str(aid)] = value
                await _save_account_scopes(db, tenant_id, scopes)
                logger.info("批量更新账号作用域 count=%s enabled=%s", len(int_ids), value)
                return ResultObject.success({"ok": True, "affected": len(int_ids), "type": "account"})

        return ResultObject.fail("需要提供 itemIds 或 accountIds 参数")
    except Exception as e:
        logger.exception("批量更新作用域失败")
        return ResultObject.fail(f"批量更新失败：{e}")


@router.get("/status")
async def get_scope_status(
    accountId: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """返回全局开关、账号级作用域配置。"""
    try:
        tenant_id = get_current_tenant_id()
        account_scopes = await _load_account_scopes(db, tenant_id)
        global_enabled = await _load_global_enabled(db, tenant_id)
        return ResultObject.success({
            "global_enabled": global_enabled,
            "account_scopes": account_scopes.get("accounts", {}),
        })
    except Exception as e:
        logger.exception("查询作用域状态失败")
        return ResultObject.fail(f"查询失败：{e}")


# ===== 内部辅助方法 =====

async def _load_account_scopes(db: AsyncSession, tenant_id: int) -> Dict[str, Any]:
    """从 user_business_setting 表读取 auto-reply-account-scopes 配置。"""
    from sqlalchemy import text
    stmt = text("SELECT config_json FROM user_business_setting WHERE tenant_id=:tid AND setting_key=:key AND deleted=0 LIMIT 1")
    result = await db.execute(stmt, {"tid": tenant_id, "key": ACCOUNT_SCOPES_KEY})
    row = result.first()
    if not row:
        return {"accounts": {}}
    try:
        config = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return config if isinstance(config, dict) else {"accounts": {}}
    except Exception:
        return {"accounts": {}}


async def _save_account_scopes(db: AsyncSession, tenant_id: int, scopes: Dict[str, Any]):
    """保存 auto-reply-account-scopes 配置到 user_business_setting 表。"""
    from sqlalchemy import text
    config_json = json.dumps(scopes, ensure_ascii=False)
    stmt = text("""
        INSERT INTO user_business_setting(tenant_id, user_id, setting_key, config_json, created_time, updated_time, deleted)
        VALUES(:tid, 0, :key, :json, NOW(), NOW(), 0)
        ON DUPLICATE KEY UPDATE config_json=VALUES(config_json), updated_time=NOW()
    """)
    await db.execute(stmt, {"tid": tenant_id, "key": ACCOUNT_SCOPES_KEY, "json": config_json})
    await db.commit()


async def _load_global_enabled(db: AsyncSession, tenant_id: int) -> bool:
    """读取 ai-customer-service.enabled 主开关状态。"""
    from sqlalchemy import text
    stmt = text("SELECT config_json FROM user_business_setting WHERE tenant_id=:tid AND setting_key='ai-customer-service' AND deleted=0 LIMIT 1")
    result = await db.execute(stmt, {"tid": tenant_id})
    row = result.first()
    if not row:
        return False
    try:
        config = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        return bool(config.get("enabled", False)) if isinstance(config, dict) else False
    except Exception:
        return False


def _compute_effective(
    product_enabled: Optional[int],
    account_id: Optional[int],
    account_scopes: Dict[str, Any],
    global_enabled: bool,
) -> bool:
    """计算商品的 effective auto_reply 状态。

    优先级：商品级 > 账号级 > 全局（NULL 不继承全局，默认关闭）。
    """
    if not global_enabled:
        return False  # 主开关关闭
    if product_enabled is not None:
        return product_enabled == 1  # 商品级覆盖
    accounts = account_scopes.get("accounts", {}) if account_scopes else {}
    if account_id is not None and str(account_id) in accounts:
        return bool(accounts[str(account_id)])  # 账号级
    return False  # 默认关闭
```

- [ ] **Step 2: 检查 tenant_context 模块是否存在**

运行: `grep -rn "get_current_tenant_id\|def get_current_tenant" apps/automation-service/app/core/`
Expected: 找到 `get_current_tenant_id` 函数。如果不存在，需要从请求头解析（参考 verify_internal_token 实现）。

如果 `tenant_context` 不存在，编辑 `auto_reply_scope.py` 顶部，将 `from app.core.tenant_context import get_current_tenant_id` 替换为内联解析：

```python
from fastapi import Request

# 在每个路由函数中添加 request: Request 参数，并解析租户ID：
# tenant_id = int(request.headers.get("X-Internal-Tenant-Id", "0"))
```

或者创建 `apps/automation-service/app/core/tenant_context.py`：

```python
from fastapi import Request

def get_current_tenant_id_from_request(request: Request) -> int:
    """从请求头 X-Internal-Tenant-Id 解析当前租户ID。"""
    raw = request.headers.get("X-Internal-Tenant-Id", "0")
    try:
        return int(raw)
    except (ValueError, TypeError):
        return 0
```

并在路由函数签名中添加 `request: Request` 参数，调用 `get_current_tenant_id_from_request(request)`。

- [ ] **Step 3: 在 api.py 注册 auto_reply_scope 路由**

编辑 `apps/automation-service/app/api/v1/api.py`，在 `from .routes import knowledge_base as knowledge_base_module` 后新增：

```python
from .routes import auto_reply_scope as auto_reply_scope_module
```

在 `api_router.include_router(knowledge_base_module.router, tags=['knowledgeBase'])` 后新增：

```python
api_router.include_router(auto_reply_scope_module.router, tags=['autoReplyScope'])
```

- [ ] **Step 4: 重启服务验证路由**

运行: 重启 automation-service，访问 `http://localhost:12401/docs`
Expected: 看到 `/api/auto-reply-scope/products`、`/api/auto-reply-scope/product`、`/api/auto-reply-scope/account`、`/api/auto-reply-scope/batch`、`/api/auto-reply-scope/status` 端点

- [ ] **Step 5: Commit**

```bash
git add apps/automation-service/app/api/v1/routes/auto_reply_scope.py apps/automation-service/app/api/v1/api.py
git commit -m "feat(python): 新增自动回复作用域管理路由（商品级/账号级/全局）"
```

---

### Task 4: 替换 items.py 的 updateAutoReplyStatus 占位实现

**Files:**
- Modify: `apps/automation-service/app/api/v1/routes/items.py` (约第 919-925 行)

- [ ] **Step 1: 替换 update_auto_reply_status 占位实现**

编辑 `apps/automation-service/app/api/v1/routes/items.py`，找到第 919-925 行的 `update_auto_reply_status` 函数，替换为调用 `auto_reply_scope` 模块的逻辑：

```python
@router.post("/updateAutoReplyStatus")
async def update_auto_reply_status(
    req: dict = {},
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
):
    """更新商品自动回复状态（兼容旧接口，实际委派给 auto_reply_scope 路由逻辑）。"""
    from app.api.v1.routes.auto_reply_scope import update_product_scope
    return await update_product_scope(req, db, _)
```

- [ ] **Step 2: Commit**

```bash
git add apps/automation-service/app/api/v1/routes/items.py
git commit -m "refactor(python): items.updateAutoReplyStatus 委派给 auto_reply_scope 模块"
```

---

## Phase 4: Java 网关层

### Task 5: 扩展 BusinessSettingsService - 优化默认值 + 新增 getDefaults

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java` (约第 100-124 行 ai-customer-service 配置)

- [ ] **Step 1: 优化 systemPrompt 和 welcomeMessage 默认值**

编辑 `apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java`，找到 `case "ai-customer-service"` 块（约第 103-124 行），将 `systemPrompt` 和 `welcomeMessage` 的默认值替换为更完整的内容：

```java
            case "ai-customer-service" -> {
                config.put("enabled", false);
                config.put("mode", "hybrid");
                config.put("workHours24", true);
                config.put("workStart", "09:00");
                config.put("workEnd", "22:00");
                config.put("persona", "专业客服");
                config.put("tone", "friendly");
                config.put("language", "zh-CN");
                config.put("replyDelaySeconds", 8);
                config.put("carryContext", true);
                config.put("pauseOnHumanIntervene", true);
                config.put("systemPrompt",
                    "你是闲鱼店铺的专业客服助手，请用友好、专业、简洁的语气回答买家问题。\n" +
                    "【身份定位】你是本店的AI客服，熟悉店铺所有商品的详情、价格、规格与售后政策。\n" +
                    "【回复原则】\n" +
                    "1. 回复简短直接，单条消息不超过80字，避免长篇大论\n" +
                    "2. 语气亲切自然，使用\"您好\"\"亲\"等称呼，避免机械化\n" +
                    "3. 涉及价格优惠时，先强调商品价值，再说明定价合理性\n" +
                    "4. 不确定的信息不要编造，引导买家咨询人工客服\n" +
                    "5. 遇到退款、投诉、维权等敏感问题，礼貌安抚后转人工处理\n" +
                    "【禁止行为】不泄露店铺内部信息、不承诺无法兑现的优惠、不与买家发生争执\n" +
                    "【转人工场景】退款投诉、账号异常、大额订单、复杂售后纠纷");
                config.put("welcomeMessage",
                    "您好~欢迎光临本店！我是AI客服小鱼，有什么可以帮您？商品拍下后48小时内发货，有任何问题随时问我哦~");
                config.put("transferThreshold", 85);
                config.put("sessionTimeoutMinutes", 30);
                config.put("blacklistKeywords", "低价、加微、微信、私聊");
                config.put("maxDailyReplies", 200);
                config.put("knowledgeBase", "");
                config.put("safeMode", true);
                config.put("handoffKeywords", "退款、投诉、赔偿、维权、差评");
            }
```

- [ ] **Step 2: 新增 getDefaults 方法**

在 `BusinessSettingsService.java` 的 `defaultConfig` 方法后新增公共方法：

```java
    /**
     * 获取指定分类的默认配置（不合并用户已保存的配置）。
     * 用于前端"恢复默认"按钮。
     */
    public Map<String, Object> getDefaults(String settingKey) {
        return defaultConfig(settingKey);
    }
```

- [ ] **Step 3: 编译验证**

运行:
```bash
cd apps/core-api
mvn compile -q
```
Expected: 编译成功，无错误

- [ ] **Step 4: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/service/BusinessSettingsService.java
git commit -m "feat(java): 优化AI客服默认值并新增getDefaults方法支持恢复默认"
```

---

### Task 6: 扩展 BusinessSettingsController - 新增 defaults 和 upload-knowledge 端点

**Files:**
- Modify: `apps/core-api/src/main/java/com/xianyu/admin/controller/BusinessSettingsController.java`

- [ ] **Step 1: 新增 /defaults 端点**

编辑 `apps/core-api/src/main/java/com/xianyu/admin/controller/BusinessSettingsController.java`，在 `testAiReply` 方法后新增：

```java
    /**
     * 获取 AI 客服配置的默认值（用于前端"恢复默认"按钮）。
     */
    @GetMapping("/ai-customer-service/defaults")
    public Result<Map<String, Object>> getAiCsDefaults() {
        return Result.ok(settingsService.getDefaults("ai-customer-service"));
    }

    /**
     * 上传知识库文件，透传到 Python automation-service 进行 AI 规则提取。
     */
    @PostMapping("/ai-customer-service/upload-knowledge")
    public Result<Object> uploadKnowledge(
            @RequestParam("file") org.springframework.web.multipart.MultipartFile file) {
        try {
            if (file == null || file.isEmpty()) {
                return Result.fail("请选择要上传的文件");
            }
            String fileName = file.getOriginalFilename();
            if (fileName == null || fileName.isBlank()) {
                return Result.fail("文件名为空");
            }
            String ext = fileName.contains(".") ? fileName.substring(fileName.lastIndexOf('.')).toLowerCase() : "";
            java.util.Set<String> allowed = java.util.Set.of(".md", ".txt", ".ppt", ".pptx", ".xlsx", ".xls", ".csv");
            if (!allowed.contains(ext)) {
                return Result.fail("不支持的文件格式：" + ext + "，仅支持 " + String.join("/", allowed));
            }
            if (file.getSize() > 10 * 1024 * 1024) {
                return Result.fail("文件不能超过 10MB（当前 " + (file.getSize() / 1024 / 1024) + "MB）");
            }

            // 透传到 Python /api/knowledge-base/extract
            Map<String, Object> result = automationClient.uploadInternalForData(
                    "/api/knowledge-base/extract",
                    file.getInputStream(),
                    fileName,
                    null
            );
            return Result.ok(result);
        } catch (Exception e) {
            log.error("知识库文件上传失败", e);
            return Result.fail("文件上传失败：" + e.getMessage());
        }
    }
```

- [ ] **Step 2: 注入 AutomationClient 依赖**

编辑 `BusinessSettingsController.java` 的构造函数（约第 35-39 行），新增 `AutomationClient` 注入：

修改前：
```java
    public BusinessSettingsController(BusinessSettingsService settingsService,
                                     AiProviderService aiProviderService) {
        this.settingsService = settingsService;
        this.aiProviderService = aiProviderService;
    }
```

修改后：
```java
    private final com.xianyu.admin.service.AutomationClient automationClient;

    public BusinessSettingsController(BusinessSettingsService settingsService,
                                     AiProviderService aiProviderService,
                                     com.xianyu.admin.service.AutomationClient automationClient) {
        this.settingsService = settingsService;
        this.aiProviderService = aiProviderService;
        this.automationClient = automationClient;
    }
```

并在类字段声明区（约第 32-33 行）新增：
```java
    private final com.xianyu.admin.service.AutomationClient automationClient;
```
（删除原 `private final` 重复声明，保持字段唯一）

- [ ] **Step 3: 优化 testAiReply 增加 errorCode**

修改 `testAiReply` 方法（约第 64-103 行），在返回的 Map 中增加 `errorCode`：

将未配置分支改为：
```java
            if (!Boolean.TRUE.equals(status.get("configured"))) {
                Map<String, Object> fallback = new LinkedHashMap<>();
                fallback.put("ok", false);
                fallback.put("reply", welcomeMessage + "（AI 模型未配置，已使用欢迎语兜底）");
                fallback.put("configured", false);
                fallback.put("errorCode", "NOT_CONFIGURED");
                return Result.ok(fallback);
            }
```

将异常分支改为：
```java
        } catch (Exception e) {
            log.error("AI 客服测试失败", e);
            Map<String, Object> err = new LinkedHashMap<>();
            err.put("ok", false);
            err.put("reply", "AI 调用失败：" + e.getMessage());
            err.put("configured", false);
            err.put("errorCode", "AI_ERROR");
            return Result.ok(err);
        }
```

- [ ] **Step 4: 编译验证**

运行:
```bash
cd apps/core-api
mvn compile -q
```
Expected: 编译成功

- [ ] **Step 5: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/controller/BusinessSettingsController.java
git commit -m "feat(java): BusinessSettingsController新增defaults和upload-knowledge端点+预览errorCode"
```

---

### Task 7: 新建 AutoReplyScopeController - Java 网关透传

**Files:**
- Create: `apps/core-api/src/main/java/com/xianyu/admin/controller/AutoReplyScopeController.java`

- [ ] **Step 1: 创建 AutoReplyScopeController.java**

写入以下完整内容：

```java
package com.xianyu.admin.controller;

import com.xianyu.admin.common.Result;
import com.xianyu.admin.service.AutomationClient;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.web.bind.annotation.*;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 自动回复作用域管理控制器。
 * 透传到 Python automation-service 的 /api/auto-reply-scope/* 路由。
 *
 * 三档作用域：商品级 > 账号级 > 全局（NULL 不继承全局，默认关闭）。
 */
@RestController
@RequestMapping("/api/auto-reply-scope")
public class AutoReplyScopeController {
    private static final Logger log = LoggerFactory.getLogger(AutoReplyScopeController.class);

    private final AutomationClient automationClient;

    public AutoReplyScopeController(AutomationClient automationClient) {
        this.automationClient = automationClient;
    }

    /**
     * 查询商品列表及 effective auto_reply 状态。
     */
    @GetMapping("/products")
    public Result<Object> listProducts(
            @RequestParam(required = false) Long accountId) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            Object data = automationClient.getInternalForData("/api/auto-reply-scope/products", query);
            return Result.ok(data);
        } catch (Exception e) {
            log.error("查询商品作用域列表失败", e);
            return Result.fail("查询失败：" + e.getMessage());
        }
    }

    /**
     * 更新单个商品的 auto_reply_enabled。
     */
    @PostMapping("/product")
    public Result<Object> updateProductScope(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> data = automationClient.postInternalForData("/api/auto-reply-scope/product", body);
            return Result.ok(data);
        } catch (Exception e) {
            log.error("更新商品作用域失败 body={}", body, e);
            return Result.fail("更新失败：" + e.getMessage());
        }
    }

    /**
     * 更新账号级 auto_reply 启用状态。
     */
    @PostMapping("/account")
    public Result<Object> updateAccountScope(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> data = automationClient.postInternalForData("/api/auto-reply-scope/account", body);
            return Result.ok(data);
        } catch (Exception e) {
            log.error("更新账号作用域失败 body={}", body, e);
            return Result.fail("更新失败：" + e.getMessage());
        }
    }

    /**
     * 批量更新商品或账号的 auto_reply 状态。
     */
    @PostMapping("/batch")
    public Result<Object> batchUpdateScope(@RequestBody Map<String, Object> body) {
        try {
            Map<String, Object> data = automationClient.postInternalForData("/api/auto-reply-scope/batch", body);
            return Result.ok(data);
        } catch (Exception e) {
            log.error("批量更新作用域失败 body={}", body, e);
            return Result.fail("批量更新失败：" + e.getMessage());
        }
    }

    /**
     * 查询全局开关和账号级作用域配置。
     */
    @GetMapping("/status")
    public Result<Object> getStatus(@RequestParam(required = false) Long accountId) {
        try {
            Map<String, Object> query = new LinkedHashMap<>();
            if (accountId != null) query.put("accountId", accountId);
            Object data = automationClient.getInternalForData("/api/auto-reply-scope/status", query);
            return Result.ok(data);
        } catch (Exception e) {
            log.error("查询作用域状态失败", e);
            return Result.fail("查询失败：" + e.getMessage());
        }
    }
}
```

- [ ] **Step 2: 编译验证**

运行:
```bash
cd apps/core-api
mvn compile -q
```
Expected: 编译成功

- [ ] **Step 3: 重启 core-api 验证端点**

运行: 重启 core-api，访问 `http://localhost:12400/api/auto-reply-scope/status`（需带认证）
Expected: 返回 401（未认证）或 200（已认证），而非 404

- [ ] **Step 4: Commit**

```bash
git add apps/core-api/src/main/java/com/xianyu/admin/controller/AutoReplyScopeController.java
git commit -m "feat(java): 新增AutoReplyScopeController透传作用域管理接口"
```

---

## Phase 5: 前端 API 层

### Task 8: 扩展 businessSettings.js + 新建 autoReplyScope.js

**Files:**
- Modify: `apps/user-web/src/api/businessSettings.js`
- Create: `apps/user-web/src/api/autoReplyScope.js`

- [ ] **Step 1: 在 businessSettings.js 末尾新增两个函数**

编辑 `apps/user-web/src/api/businessSettings.js`，在 `export const BUSINESS_SETTING_CATEGORIES = CATEGORIES` 后新增：

```javascript
/**
 * 获取 AI 客服配置的默认值（用于"恢复默认"按钮）。
 */
export function getAiCsDefaults() {
  return request.get('/business-settings/ai-customer-service/defaults')
}

/**
 * 上传知识库文件，由 AI 自动提取回复规则。
 * @param {File} file 用户选择的文件（.md/.ppt/.pptx/.xlsx/.xls/.csv）
 */
export function uploadKnowledgeBase(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/business-settings/ai-customer-service/upload-knowledge', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}
```

- [ ] **Step 2: 创建 autoReplyScope.js**

写入以下完整内容：

```javascript
import request from '../utils/request.js'

/**
 * 查询商品列表及每个商品的 effective auto_reply 状态。
 * @param {number} [accountId] 账号ID，不传则返回全部账号商品
 */
export function getAutoReplyScopeProducts(accountId) {
  const params = {}
  if (accountId != null) params.accountId = accountId
  return request.get('/auto-reply-scope/products', { params })
}

/**
 * 更新单个商品的 auto_reply_enabled。
 * @param {number} itemId 商品ID
 * @param {boolean} enabled 启用状态
 */
export function updateProductAutoReplyScope(itemId, enabled) {
  return request.post('/auto-reply-scope/product', { itemId, enabled })
}

/**
 * 更新账号级 auto_reply 启用状态。
 * @param {number} accountId 账号ID
 * @param {boolean} enabled 启用状态
 */
export function updateAccountAutoReplyScope(accountId, enabled) {
  return request.post('/auto-reply-scope/account', { accountId, enabled })
}

/**
 * 批量更新商品或账号的 auto_reply 状态。
 * @param {Object} body - {itemIds: [], enabled} 或 {accountIds: [], enabled}
 */
export function batchUpdateAutoReplyScope(body) {
  return request.post('/auto-reply-scope/batch', body)
}

/**
 * 查询全局开关和账号级作用域配置。
 * @param {number} [accountId] 账号ID
 */
export function getAutoReplyScopeStatus(accountId) {
  const params = {}
  if (accountId != null) params.accountId = accountId
  return request.get('/auto-reply-scope/status', { params })
}
```

- [ ] **Step 3: 验证 import 可用**

运行: 在 user-web 项目 dev server 控制台执行 `import('./src/api/autoReplyScope.js')`
Expected: 无报错

- [ ] **Step 4: Commit**

```bash
git add apps/user-web/src/api/businessSettings.js apps/user-web/src/api/autoReplyScope.js
git commit -m "feat(web): 新增AI客服默认值/文件上传API和作用域管理API封装"
```

---

## Phase 6: AiCsSettings.vue 改造

### Task 9: AiCsSettings.vue - 知识库大段文本 + 字符计数

**Files:**
- Modify: `apps/user-web/src/pages/settings/AiCsSettings.vue`

- [ ] **Step 1: 升级 knowledgeBase textarea**

编辑 `apps/user-web/src/pages/settings/AiCsSettings.vue`，找到第 100-102 行的知识库字段：

```html
            <div class="aics-row">
              <label>知识库（可选）</label>
              <textarea v-model="form.knowledgeBase" class="aics-input aics-textarea" rows="4" placeholder="常见问题、售后政策、商品参数，每行一条" />
            </div>
```

替换为：

```html
            <div class="aics-row">
              <label>知识库（可选）</label>
              <textarea v-model="form.knowledgeBase" class="aics-input aics-textarea aics-kb-textarea" rows="12" placeholder="可输入大段文字描述客服规则、售后政策、商品参数等；也可上传文件由 AI 自动提取"></textarea>
              <div class="aics-kb-footer">
                <span class="aics-kb-count">已输入 {{ (form.knowledgeBase || '').length }} 字</span>
              </div>
            </div>
```

- [ ] **Step 2: 在 style 块新增样式**

在 `<style scoped>` 块中（约第 325 行 `.aics-textarea` 样式后）新增：

```css
.aics-kb-textarea { min-height: 240px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; line-height: 1.6; }
.aics-kb-footer { display: flex; justify-content: flex-end; margin-top: 4px; }
.aics-kb-count { font-size: 11px; color: #99a4b4; }
```

- [ ] **Step 3: 验证页面渲染**

运行: 刷新 user-web，进入 AI 客服配置页面
Expected: 知识库文本框扩大为 12 行，显示字符计数

- [ ] **Step 4: Commit**

```bash
git add apps/user-web/src/pages/settings/AiCsSettings.vue
git commit -m "style(web): 知识库文本框扩大为12行并显示字符计数"
```

---

### Task 10: AiCsSettings.vue - 文件上传 + AI 提取

**Files:**
- Modify: `apps/user-web/src/pages/settings/AiCsSettings.vue`

- [ ] **Step 1: 在知识库字段后新增文件上传区域**

编辑 `apps/user-web/src/pages/settings/AiCsSettings.vue`，在上一步的 `<div class="aics-kb-footer">...</div>` 后新增文件上传区域：

```html
            <div class="aics-upload-area">
              <input ref="kbFileInputRef" type="file" accept=".md,.txt,.ppt,.pptx,.xlsx,.xls,.csv" style="display:none" @change="onKbFileChange" />
              <button type="button" class="aics-upload-btn" :disabled="kbUploading" @click="kbFileInputRef?.click()">
                {{ kbUploading ? '正在提取...' : '📤 上传文件提取规则' }}
              </button>
              <span class="aics-upload-hint">支持 .md / .ppt / .pptx / .xlsx / .xls / .csv，单文件 ≤10MB</span>
            </div>
```

- [ ] **Step 2: 在 script 中新增上传逻辑**

编辑 `AiCsSettings.vue` 的 `<script setup>` 部分，在 `import` 行（约第 193 行）新增导入：

```javascript
import { getAiCsDefaults, uploadKnowledgeBase } from '../../api/businessSettings.js'
```

在 `const testConfigured = ref(null)` 后（约第 201 行）新增：

```javascript
const kbFileInputRef = ref(null)
const kbUploading = ref(false)
```

在 `function openTestPanel()` 前新增上传函数：

```javascript
async function onKbFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  if (file.size > 10 * 1024 * 1024) {
    showToast('文件不能超过 10MB', true)
    return
  }
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  if (!['.md', '.txt', '.ppt', '.pptx', '.xlsx', '.xls', '.csv'].includes(ext)) {
    showToast('仅支持 .md / .ppt / .pptx / .xlsx / .xls / .csv', true)
    return
  }
  kbUploading.value = true
  try {
    const res = await uploadKnowledgeBase(file)
    const data = res?.data ?? res
    const extractedText = data?.extractedText || ''
    const ruleCount = data?.ruleCount || 0
    const fileName = data?.fileName || file.name
    if (!extractedText) {
      showToast('AI 未能从文件中提取有效规则', true)
      return
    }
    const separator = form.knowledgeBase ? '\n\n---\n\n' : ''
    form.knowledgeBase = (form.knowledgeBase || '') + separator + `<!-- 来自文件：${fileName} -->\n` + extractedText
    showToast(`已从 ${fileName} 提取 ${ruleCount} 条规则，已追加到知识库`)
  } catch (err) {
    showToast('文件上传失败：' + (err.message || '网络错误'), true)
  } finally {
    kbUploading.value = false
  }
}
```

- [ ] **Step 3: 在 style 块新增上传区样式**

在 `<style scoped>` 中新增：

```css
.aics-upload-area { display: flex; align-items: center; gap: 10px; margin-top: 8px; padding: 10px; border: 1px dashed #dbe6f6; border-radius: 10px; background: #fafbfc; }
.aics-upload-btn { padding: 6px 14px; border-radius: 8px; border: 1px solid #bfdbfe; background: #fff; color: #2563eb; font-size: 12px; font-weight: 600; cursor: pointer; transition: all .2s; }
.aics-upload-btn:hover:not(:disabled) { background: #eff6ff; }
.aics-upload-btn:disabled { opacity: .6; cursor: not-allowed; }
.aics-upload-hint { font-size: 11px; color: #99a4b4; }
```

- [ ] **Step 4: 验证上传功能**

运行: 刷新页面，点击"上传文件提取规则"按钮，选择一个 .md 文件
Expected: 显示"正在提取..."，完成后 Toast 提示"已从 xxx.md 提取 N 条规则"，文本框追加提取的内容

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/settings/AiCsSettings.vue
git commit -m "feat(web): AiCsSettings支持知识库文件上传与AI规则提取"
```

---

### Task 11: AiCsSettings.vue - 恢复默认按钮

**Files:**
- Modify: `apps/user-web/src/pages/settings/AiCsSettings.vue`

- [ ] **Step 1: 在系统提示词和欢迎语字段旁加"恢复默认"按钮**

编辑 `AiCsSettings.vue`，找到系统提示词字段（约第 91-94 行）：

```html
            <div class="aics-row">
              <label>系统提示词（System Prompt）</label>
              <textarea v-model="form.systemPrompt" class="aics-input aics-textarea" rows="4" placeholder="定义 AI 的角色、店铺信息、商品特色与回复边界" />
            </div>
```

替换为：

```html
            <div class="aics-row">
              <div class="aics-label-row">
                <label>系统提示词（System Prompt）</label>
                <button type="button" class="aics-restore-btn" @click="restoreDefault('systemPrompt')">恢复默认</button>
              </div>
              <textarea v-model="form.systemPrompt" class="aics-input aics-textarea" rows="4" placeholder="定义 AI 的角色、店铺信息、商品特色与回复边界" />
            </div>
```

找到欢迎语字段（约第 95-98 行）：

```html
            <div class="aics-row">
              <label>欢迎语</label>
              <textarea v-model="form.welcomeMessage" class="aics-input aics-textarea" rows="2" placeholder="新会话进入时自动发送" />
            </div>
```

替换为：

```html
            <div class="aics-row">
              <div class="aics-label-row">
                <label>欢迎语</label>
                <button type="button" class="aics-restore-btn" @click="restoreDefault('welcomeMessage')">恢复默认</button>
              </div>
              <textarea v-model="form.welcomeMessage" class="aics-input aics-textarea" rows="2" placeholder="新会话进入时自动发送" />
            </div>
```

- [ ] **Step 2: 新增 restoreDefault 函数**

在 `<script setup>` 中（`onKbFileChange` 函数后或 `function openTestPanel()` 前）新增：

```javascript
async function restoreDefault(field) {
  if (!['systemPrompt', 'welcomeMessage'].includes(field)) return
  if (!await confirmAction(`恢复默认将覆盖当前${field === 'systemPrompt' ? '系统提示词' : '欢迎语'}内容，是否继续？`)) return
  try {
    const res = await getAiCsDefaults()
    const data = res?.data ?? res
    if (data && data[field] !== undefined) {
      form[field] = data[field]
      showToast('已恢复默认值，请点击"保存配置"以生效')
    }
  } catch (err) {
    showToast('恢复默认失败：' + (err.message || '网络错误'), true)
  }
}

async function confirmAction(msg) {
  try { return await window.confirm(msg) } catch (e) { return true }
}
```

注意：如果项目中已有 `confirmAction` 工具函数（如 `apps/user-web/src/utils/confirmAction.js`），则直接 import 使用，不要重复定义。检查方式：
```bash
grep -rn "confirmAction" apps/user-web/src/utils/confirmAction.js
```
如果存在，移除上方的 `confirmAction` 本地定义，改为：
```javascript
import { confirmAction } from '../../utils/confirmAction.js'
```

- [ ] **Step 3: 在 style 块新增按钮样式**

```css
.aics-label-row { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.aics-restore-btn { padding: 2px 8px; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff; color: #6b7a90; font-size: 11px; cursor: pointer; transition: all .2s; }
.aics-restore-btn:hover { color: #2563eb; border-color: #bfdbfe; }
```

- [ ] **Step 4: 验证恢复默认**

运行: 刷新页面，点击系统提示词旁的"恢复默认"按钮
Expected: 弹出确认框，确认后系统提示词填入优化后的默认值

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/settings/AiCsSettings.vue
git commit -m "feat(web): AiCsSettings新增恢复默认按钮"
```

---

### Task 12: AiCsSettings.vue - 实时回复预览错误提示优化

**Files:**
- Modify: `apps/user-web/src/pages/settings/AiCsSettings.vue`

- [ ] **Step 1: 改造 runTest 函数**

编辑 `AiCsSettings.vue`，找到 `runTest` 函数（约第 265-288 行），替换为：

```javascript
async function runTest() {
  if (!testMessage.value.trim()) return
  testing.value = true
  testError.value = ''
  testReply.value = ''
  testConfigured.value = null
  try {
    const res = await testAiCustomerService(testMessage.value.trim())
    const data = res?.data ?? res
    if (data?.ok) {
      testReply.value = data.reply || '（无回复内容）'
    } else {
      testReply.value = data?.reply || ''
      const errorCode = data?.errorCode
      if (errorCode === 'NOT_CONFIGURED' || data?.configured === false) {
        testConfigured.value = false
      } else if (errorCode === 'AI_ERROR') {
        testError.value = 'AI 调用失败：' + (data?.reply || '未知错误')
      } else {
        testError.value = data?.reply ? '' : 'AI 未返回有效回复'
      }
    }
  } catch (e) {
    testError.value = '网络异常，请检查网络连接后重试'
    testConfigured.value = 'NETWORK_ERROR'
  } finally {
    testing.value = false
  }
}
```

- [ ] **Step 2: 改造模板中的错误提示区**

找到实时回复预览的错误提示部分（约第 161-162 行）：

```html
          <p v-if="testError" class="aics-error">{{ testError }}</p>
          <p v-if="testConfigured === false" class="aics-warn">⚠ AI 模型未配置，请到「后台 → 模型配置」先配置通用文本模型</p>
```

替换为：

```html
          <div v-if="testError" class="aics-error-box">
            <p class="aics-error">{{ testError }}</p>
            <button type="button" class="aics-retry-btn" :disabled="testing" @click="runTest">{{ testing ? '重试中...' : '重试' }}</button>
          </div>
          <div v-if="testConfigured === false" class="aics-warn-box">
            <p class="aics-warn">⚠ AI 模型未配置，请到「后台 → 模型配置」先配置通用文本模型</p>
            <button type="button" class="aics-retry-btn" @click="goToModelConfig">前往模型配置</button>
          </div>
          <div v-if="testConfigured === 'NETWORK_ERROR'" class="aics-error-box">
            <p class="aics-error">网络异常，请检查网络连接</p>
            <button type="button" class="aics-retry-btn" :disabled="testing" @click="runTest">{{ testing ? '重试中...' : '重试' }}</button>
          </div>
```

- [ ] **Step 3: 新增 goToModelConfig 函数**

在 `runTest` 函数后新增：

```javascript
function goToModelConfig() {
  // 跳转到 admin-web 模型配置页面（或触发导航事件）
  // 如果有全局导航事件机制：
  window.dispatchEvent(new CustomEvent('xya-navigate', { detail: { route: 'ai-model-config' } }))
  // 如果没有，则打开新窗口到 admin-web
  window.open('/admin/#/ai-provider', '_blank')
}
```

注意：实际跳转路径需根据项目路由配置调整。如果 user-web 内有模型配置页，则用 `emit` 或导航事件跳转。

- [ ] **Step 4: 新增样式**

```css
.aics-error-box, .aics-warn-box { display: flex; flex-direction: column; gap: 8px; padding: 10px; border-radius: 8px; margin-top: 8px; }
.aics-error-box { background: #fef2f2; border: 1px solid #fecaca; }
.aics-warn-box { background: #fffbeb; border: 1px solid #fde68a; }
.aics-retry-btn { align-self: flex-start; padding: 4px 12px; border-radius: 6px; border: 1px solid #dbe6f6; background: #fff; color: #2563eb; font-size: 12px; cursor: pointer; }
.aics-retry-btn:hover:not(:disabled) { background: #eff6ff; }
.aics-retry-btn:disabled { opacity: .6; cursor: not-allowed; }
```

- [ ] **Step 5: 验证预览错误提示**

运行: 刷新页面，点击"生成回复"
Expected: 根据后端 errorCode 显示对应的错误提示（未配置/AI异常/网络错误），提供跳转或重试按钮

- [ ] **Step 6: Commit**

```bash
git add apps/user-web/src/pages/settings/AiCsSettings.vue
git commit -m "feat(web): AiCsSettings实时回复预览错误提示优化，区分未配置/AI异常/网络错误"
```

---

## Phase 7: ProductsPage.vue 改造

### Task 13: ProductsPage.vue - 自动回复开关直接生效 + 前置校验

**Files:**
- Modify: `apps/user-web/src/pages/ProductsPage.vue`

- [ ] **Step 1: 在 script 中导入作用域 API 和 businessSettings**

编辑 `apps/user-web/src/pages/ProductsPage.vue`，找到 import 区（约第 203-210 行），在末尾新增：

```javascript
import { getBusinessSettings } from '../api/businessSettings.js'
import { updateProductAutoReplyScope, batchUpdateAutoReplyScope } from '../api/autoReplyScope.js'
```

- [ ] **Step 2: 新增 aiCsEnabled 缓存和前置校验函数**

在 `const autoReplyOnCount = computed(...)` 后（约第 295 行后）新增：

```javascript
const aiCsEnabledCache = ref(null)

async function checkAiCsEnabled() {
  if (aiCsEnabledCache.value !== null) return aiCsEnabledCache.value
  try {
    const res = await getBusinessSettings('ai-customer-service')
    const data = res?.data ?? res
    aiCsEnabledCache.value = data?.enabled === true
    return aiCsEnabledCache.value
  } catch (e) {
    console.warn('[ProductsPage] 检查AI客服主开关失败', e)
    return false
  }
}

function promptEnableAiCs() {
  if (!window.confirm('⚠ 尚未开启 AI 自动回复主开关\n\n请先前往「AI 客服配置」页面开启 24 小时全天在线的 AI 自动回复\n\n点击"确定"前往配置，点击"取消"返回。')) return
  emit('navigate', 'settings-ai-cs')
}
```

- [ ] **Step 3: 替换 toggleReply 函数**

找到 `function toggleReply(row) { emit('navigate', 'auto-reply') }`（约第 422 行），替换为：

```javascript
async function toggleReply(row) {
  if (await isItemBusy(row)) return
  const nextEnabled = !row.replyOn
  if (nextEnabled) {
    const enabled = await checkAiCsEnabled()
    if (!enabled) {
      promptEnableAiCs()
      return
    }
  }
  try {
    await updateProductAutoReplyScope(row.raw.id, nextEnabled)
    row.replyOn = nextEnabled
    row.raw.auto_reply_enabled = nextEnabled ? 1 : 0
    showNotice('success', `已${nextEnabled ? '开启' : '关闭'}商品"${row.name}"的自动回复`)
    aiCsEnabledCache.value = null  // 刷新缓存
  } catch (e) {
    showNotice('error', e.message || '切换自动回复失败')
    aiCsEnabledCache.value = null
  }
}
```

注意：`row.raw.id` 是商品的数据库ID。如果 ProductsPage 中商品ID字段不同，需根据 `row.raw` 的实际结构调整（可能是 `row.raw.id` 或 `row.raw.goodsId`）。请检查 `products` computed 中的数据来源。

- [ ] **Step 4: 验证自动回复开关**

运行: 刷新商品管理页面，点击某个商品的自动回复开关
Expected: 若AI客服未开启，弹出引导确认框；若已开启，直接切换并提示成功

- [ ] **Step 5: Commit**

```bash
git add apps/user-web/src/pages/ProductsPage.vue
git commit -m "feat(web): ProductsPage自动回复开关直接生效，开启前校验AI客服主开关"
```

---

## Phase 8: AutoReplyPage.vue 重构

### Task 14: AutoReplyPage.vue - 完整重构为双列+极简面板

**Files:**
- Modify: `apps/user-web/src/pages/AutoReplyPage.vue`

- [ ] **Step 1: 完整替换 AutoReplyPage.vue 的 template**

编辑 `apps/user-web/src/pages/AutoReplyPage.vue`，将 `<template>` 部分整体替换为：

```html
<template>
  <div class="auto-reply-wrap">
    <div v-if="error" class="global-notice error">{{ error }}</div>
    <div v-if="success" class="global-notice success">{{ success }}</div>

    <div class="ar-grid">
      <!-- 左栏：账号列 + 商品列 -->
      <div class="ar-left">
        <CardPanel title="账号">
          <div class="ar-account-list">
            <div
              :class="['ar-account-item', { active: selectedAccountId === '' }]"
              @click="selectAccount('')"
            >
              <span class="ar-account-icon">📂</span>
              <span>全部账号</span>
            </div>
            <div
              v-for="a in accounts"
              :key="a.id"
              :class="['ar-account-item', { active: selectedAccountId === a.id }]"
              @click="selectAccount(a.id)"
            >
              <span class="ar-account-icon">👤</span>
              <span>{{ accountName(a) }}</span>
              <Badge v-if="accountScopeStatus[a.id] === true" type="green">已启用</Badge>
              <Badge v-else-if="accountScopeStatus[a.id] === false" type="gray">未启用</Badge>
            </div>
          </div>
        </CardPanel>

        <CardPanel title="商品" style="margin-top:16px">
          <div class="ar-product-toolbar">
            <input v-model="productSearch" class="ar-search-input" placeholder="搜索商品标题..." />
            <AppButton type="primary" :disabled="batchUpdating" @click="batchEnableAllProducts">
              {{ batchUpdating ? '处理中...' : '一键全部开启' }}
            </AppButton>
          </div>
          <div v-if="productsLoading" class="ar-loading">商品加载中...</div>
          <div v-else-if="!filteredProducts.length" class="ar-empty">暂无商品</div>
          <div v-else class="ar-product-list">
            <label
              v-for="p in filteredProducts"
              :key="p.id"
              :class="['ar-product-item', { selected: selectedProductIds.includes(p.id) }]"
            >
              <input
                type="checkbox"
                :checked="selectedProductIds.includes(p.id)"
                @change="toggleProductSelect(p.id)"
              />
              <div class="ar-product-info">
                <b :title="p.title">{{ shortText(p.title, 30) }}</b>
                <div class="ar-product-status">
                  <Badge v-if="p.auto_reply_enabled === 1" type="green">已开启</Badge>
                  <Badge v-else-if="p.auto_reply_enabled === 0" type="gray">已关闭</Badge>
                  <Badge v-else-if="p.account_enabled === true" type="blue">继承账号级</Badge>
                  <Badge v-else type="gray">未开启</Badge>
                  <span class="ar-product-effective" :class="{ on: p.effective_enabled }">
                    {{ p.effective_enabled ? '生效中' : '未生效' }}
                  </span>
                </div>
              </div>
            </label>
          </div>
        </CardPanel>
      </div>

      <!-- 右栏：极简策略面板 -->
      <div class="ar-right">
        <CardPanel title="自动回复策略">
          <div class="ar-scope-info">
            <span class="ar-scope-label">当前作用域：</span>
            <b class="ar-scope-value">{{ currentScopeText }}</b>
          </div>

          <div class="ar-toggle-row">
            <div>
              <strong>启用自动回复</strong>
              <p v-if="selectedAccountId === '' && !selectedProductIds.length">开启后，所有账号的自动回复能力被激活</p>
              <p v-else-if="selectedProductIds.length === 1">仅对该商品生效</p>
              <p v-else-if="selectedProductIds.length > 1">批量切换 {{ selectedProductIds.length }} 个商品</p>
              <p v-else>仅对该账号下的商品生效</p>
            </div>
            <ToggleSwitch :on="currentScopeEnabled" @click="toggleCurrentScope" />
          </div>
        </CardPanel>

        <CardPanel title="AI 客服配置摘要" style="margin-top:16px">
          <div v-if="aiCsSummary" class="ar-cs-summary">
            <div class="ar-cs-field">
              <label>系统提示词</label>
              <p class="ar-cs-text">{{ shortText(aiCsSummary.systemPrompt, 120) }}</p>
            </div>
            <div class="ar-cs-field">
              <label>欢迎语</label>
              <p class="ar-cs-text">{{ shortText(aiCsSummary.welcomeMessage, 60) }}</p>
            </div>
            <div class="ar-cs-field">
              <label>知识库</label>
              <p class="ar-cs-text">{{ aiCsSummary.knowledgeBase ? `已配置（${(aiCsSummary.knowledgeBase).length} 字）` : '未配置' }}</p>
            </div>
            <AppButton @click="goToAiCsSettings">前往 AI 客服配置修改</AppButton>
          </div>
          <div v-else class="ar-loading">加载中...</div>
        </CardPanel>

        <CardPanel v-if="selectedProductIds.length > 1" title="批量操作" style="margin-top:16px">
          <div class="ar-batch-actions">
            <AppButton type="primary" :disabled="batchUpdating" @click="batchUpdateProducts(true)">为选中商品开启</AppButton>
            <AppButton :disabled="batchUpdating" @click="batchUpdateProducts(false)">为选中商品关闭</AppButton>
          </div>
        </CardPanel>
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 完整替换 AutoReplyPage.vue 的 script**

将 `<script setup>` 部分整体替换为：

```javascript
<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import CardPanel from '../components/CardPanel.vue'
import Badge from '../components/Badge.vue'
import AppButton from '../components/AppButton.vue'
import ToggleSwitch from '../components/ToggleSwitch.vue'
import { getAccounts } from '../api/accounts.js'
import { getBusinessSettings } from '../api/businessSettings.js'
import {
  getAutoReplyScopeProducts,
  getAutoReplyScopeStatus,
  updateProductAutoReplyScope,
  updateAccountAutoReplyScope,
  batchUpdateAutoReplyScope
} from '../api/autoReplyScope.js'
import { accountName, shortText } from '../utils/format.js'
import { recordsOf } from '../utils/apiData.js'

const emit = defineEmits(['navigate'])

const accounts = ref([])
const selectedAccountId = ref('')  // '' = 全部账号
const selectedProductIds = ref([])
const products = ref([])
const productsLoading = ref(false)
const productSearch = ref('')
const accountScopeStatus = ref({})  // {accountId: bool}
const globalEnabled = ref(false)
const aiCsSummary = ref(null)
const batchUpdating = ref(false)
const error = ref('')
const success = ref('')

const filteredProducts = computed(() => {
  if (!productSearch.value.trim()) return products.value
  const kw = productSearch.value.trim().toLowerCase()
  return products.value.filter(p => (p.title || '').toLowerCase().includes(kw))
})

const currentScopeText = computed(() => {
  if (selectedProductIds.value.length === 1) {
    const p = products.value.find(x => x.id === selectedProductIds.value[0])
    return `商品：${p ? shortText(p.title, 20) : ''}`
  }
  if (selectedProductIds.value.length > 1) return `已选 ${selectedProductIds.value.length} 个商品`
  if (selectedAccountId.value === '') return '全部账号（全局）'
  const a = accounts.value.find(x => x.id === selectedAccountId.value)
  return `账号：${accountName(a || {})}`
})

const currentScopeEnabled = computed(() => {
  if (selectedProductIds.value.length === 1) {
    const p = products.value.find(x => x.id === selectedProductIds.value[0])
    return p?.auto_reply_enabled === 1
  }
  if (selectedProductIds.value.length > 1) return false
  if (selectedAccountId.value !== '') {
    return accountScopeStatus.value[selectedAccountId.value] === true
  }
  return globalEnabled.value
})

async function loadAccounts() {
  try {
    const res = await getAccounts()
    accounts.value = recordsOf(res.data)
  } catch (e) {
    error.value = '账号加载失败：' + (e.message || '')
  }
}

async function loadScopeStatus() {
  try {
    const res = await getAutoReplyScopeStatus()
    const data = res?.data ?? res
    globalEnabled.value = data?.global_enabled === true
    accountScopeStatus.value = data?.account_scopes || {}
  } catch (e) {
    console.warn('[AutoReply] 加载作用域状态失败', e)
  }
}

async function loadAiCsSummary() {
  try {
    const res = await getBusinessSettings('ai-customer-service')
    const data = res?.data ?? res
    aiCsSummary.value = data
  } catch (e) {
    console.warn('[AutoReply] 加载AI客服摘要失败', e)
  }
}

async function loadProducts() {
  productsLoading.value = true
  selectedProductIds.value = []
  try {
    const accountId = selectedAccountId.value === '' ? undefined : selectedAccountId.value
    const res = await getAutoReplyScopeProducts(accountId)
    const data = res?.data ?? res
    products.value = data?.items || []
  } catch (e) {
    error.value = '商品加载失败：' + (e.message || '')
    products.value = []
  } finally {
    productsLoading.value = false
  }
}

function selectAccount(accountId) {
  selectedAccountId.value = accountId
  selectedProductIds.value = []
  loadProducts()
}

function toggleProductSelect(id) {
  const idx = selectedProductIds.value.indexOf(id)
  if (idx >= 0) selectedProductIds.value.splice(idx, 1)
  else selectedProductIds.value.push(id)
}

async function toggleCurrentScope() {
  const nextEnabled = !currentScopeEnabled.value
  try {
    if (selectedProductIds.value.length === 1) {
      const id = selectedProductIds.value[0]
      await updateProductAutoReplyScope(id, nextEnabled)
      const p = products.value.find(x => x.id === id)
      if (p) p.auto_reply_enabled = nextEnabled ? 1 : 0
      success.value = `已${nextEnabled ? '开启' : '关闭'}商品自动回复`
    } else if (selectedProductIds.value.length > 1) {
      await batchUpdateAutoReplyScope({ itemIds: selectedProductIds.value, enabled: nextEnabled })
      products.value.forEach(p => {
        if (selectedProductIds.value.includes(p.id)) p.auto_reply_enabled = nextEnabled ? 1 : 0
      })
      success.value = `已${nextEnabled ? '开启' : '关闭'} ${selectedProductIds.value.length} 个商品`
    } else if (selectedAccountId.value !== '') {
      await updateAccountAutoReplyScope(selectedAccountId.value, nextEnabled)
      accountScopeStatus.value[selectedAccountId.value] = nextEnabled
      success.value = `已${nextEnabled ? '开启' : '关闭'}该账号的自动回复`
      await loadProducts()  // 刷新商品列表的 effective 状态
    } else {
      // 全局开关 - 跳转到 AI 客服配置页
      if (!window.confirm('全局主开关需在「AI 客服配置」页面开启，是否前往？')) return
      emit('navigate', 'settings-ai-cs')
      return
    }
    setTimeout(() => { success.value = '' }, 3000)
  } catch (e) {
    error.value = '切换失败：' + (e.message || '网络错误')
    setTimeout(() => { error.value = '' }, 3000)
  }
}

async function batchUpdateProducts(enabled) {
  if (!selectedProductIds.value.length) return
  batchUpdating.value = true
  try {
    await batchUpdateAutoReplyScope({ itemIds: selectedProductIds.value, enabled })
    products.value.forEach(p => {
      if (selectedProductIds.value.includes(p.id)) p.auto_reply_enabled = enabled ? 1 : 0
    })
    success.value = `已${enabled ? '开启' : '关闭'} ${selectedProductIds.value.length} 个商品`
    setTimeout(() => { success.value = '' }, 3000)
  } catch (e) {
    error.value = '批量操作失败：' + (e.message || '')
  } finally {
    batchUpdating.value = false
  }
}

async function batchEnableAllProducts() {
  if (!products.value.length) return
  if (!window.confirm(`将为当前列表的 ${products.value.length} 个商品全部开启自动回复，确认？`)) return
  batchUpdating.value = true
  try {
    const allIds = products.value.map(p => p.id)
    await batchUpdateAutoReplyScope({ itemIds: allIds, enabled: true })
    products.value.forEach(p => { p.auto_reply_enabled = 1 })
    success.value = `已为 ${allIds.length} 个商品开启自动回复`
    setTimeout(() => { success.value = '' }, 3000)
  } catch (e) {
    error.value = '一键开启失败：' + (e.message || '')
  } finally {
    batchUpdating.value = false
  }
}

function goToAiCsSettings() {
  emit('navigate', 'settings-ai-cs')
}

onMounted(async () => {
  await loadAccounts()
  await Promise.all([loadScopeStatus(), loadAiCsSummary(), loadProducts()])
})
</script>
```

- [ ] **Step 3: 完整替换 style**

将 `<style scoped>` 部分整体替换为：

```css
.auto-reply-wrap { max-width: 100%; }
.ar-grid { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 18px; align-items: start; }

.ar-left { display: flex; flex-direction: column; gap: 0; }
.ar-account-list { display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; }
.ar-account-item { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background .2s; font-size: 13px; }
.ar-account-item:hover { background: #f6f9ff; }
.ar-account-item.active { background: #eff6ff; color: #2563eb; font-weight: 600; }
.ar-account-icon { font-size: 14px; }

.ar-product-toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.ar-search-input { flex: 1; height: 32px; padding: 0 10px; border: 1px solid #dbe6f6; border-radius: 8px; font-size: 12px; outline: 0; }
.ar-search-input:focus { border-color: #2563eb; }

.ar-loading { padding: 20px; text-align: center; color: #6b7a90; font-size: 12px; }
.ar-empty { padding: 20px; text-align: center; color: #99a4b4; font-size: 12px; }
.ar-product-list { display: flex; flex-direction: column; gap: 4px; max-height: 400px; overflow-y: auto; }
.ar-product-item { display: flex; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background .2s; }
.ar-product-item:hover { background: #f6f9ff; }
.ar-product-item.selected { background: #eff6ff; }
.ar-product-info { display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0; }
.ar-product-info b { font-size: 13px; color: #172b4d; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ar-product-status { display: flex; align-items: center; gap: 6px; }
.ar-product-effective { font-size: 11px; color: #99a4b4; }
.ar-product-effective.on { color: #16a34a; }

.ar-right { display: flex; flex-direction: column; gap: 0; }
.ar-scope-info { display: flex; align-items: center; gap: 8px; padding: 8px 0 16px; border-bottom: 1px solid #f1f5f9; margin-bottom: 16px; }
.ar-scope-label { font-size: 12px; color: #6b7a90; }
.ar-scope-value { font-size: 14px; color: #172b4d; }

.ar-toggle-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 0; }
.ar-toggle-row strong { font-size: 14px; color: #172b4d; }
.ar-toggle-row p { font-size: 12px; color: #6b7a90; margin: 4px 0 0; }

.ar-cs-summary { display: flex; flex-direction: column; gap: 12px; }
.ar-cs-field label { font-size: 12px; color: #6b7a90; font-weight: 600; }
.ar-cs-text { font-size: 13px; color: #172b4d; margin: 4px 0 0; line-height: 1.5; }

.ar-batch-actions { display: flex; gap: 10px; }

.global-notice { padding: 10px 14px; border-radius: 10px; margin-bottom: 16px; font-size: 13px; }
.global-notice.error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
.global-notice.success { background: #ecfdf3; color: #067647; border: 1px solid #abefc6; }

@media (max-width: 1100px) {
  .ar-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 4: 验证页面渲染**

运行: 刷新自动回复页面
Expected: 左侧显示账号列+商品列，右侧显示极简策略面板+AI客服配置摘要；选账号/商品时右侧作用域文本更新

- [ ] **Step 5: 验证作用域切换**

测试场景：
1. 选"全部账号"→ 右侧显示"全部账号（全局）"，点击开关提示前往AI客服配置
2. 选单一账号 → 右侧显示"账号：xxx"，点击开关切换账号级enabled
3. 选单个商品 → 右侧显示"商品：xxx"，点击开关切换商品级enabled
4. 多选商品 → 右侧显示"已选N个商品"，出现批量操作卡片

Expected: 各场景作用域切换正确

- [ ] **Step 6: Commit**

```bash
git add apps/user-web/src/pages/AutoReplyPage.vue
git commit -m "feat(web): AutoReplyPage重构为双列布局+极简策略面板，移除规则字段"
```

---

## Phase 9: 联调验证

### Task 15: 端到端联调验证

**Files:**
- 无文件修改，仅验证

- [ ] **Step 1: 验证AI客服配置页面完整流程**

1. 进入 AI 客服配置页面
2. 点击系统提示词旁"恢复默认"→ 确认 → 填入优化后的默认值
3. 在知识库文本框输入大段文字 → 字符计数正确
4. 点击"上传文件提取规则"→ 选择 .md 文件 → Toast 提示提取成功 → 文本框追加提取内容
5. 保存配置 → 成功
6. 点击"生成回复"→ 根据AI配置状态显示对应提示

- [ ] **Step 2: 验证商品管理页面开关**

1. 进入商品管理页面
2. 若AI客服主开关未开启 → 点击商品自动回复开关 → 弹出引导确认框 → 点击"确定"跳转到AI客服配置
3. 在AI客服配置页开启主开关 → 保存
4. 回到商品管理 → 点击商品自动回复开关 → 直接切换成功，Toast 提示
5. 商品列表的"自动回复"列状态正确更新

- [ ] **Step 3: 验证自动回复页面作用域**

1. 进入自动回复页面
2. 选"全部账号"→ 商品列显示全部商品 → 右侧显示"全部账号（全局）"
3. 选单一账号 → 商品列显示该账号商品 → 右侧显示"账号：xxx"
4. 选单个商品 → 右侧显示"商品：xxx"→ 点击开关 → 商品级enabled切换
5. 多选商品 → 出现批量操作卡片 → "为选中商品开启"→ 批量切换成功
6. 点击"一键全部开启"→ 确认 → 当前列表所有商品开启
7. 点击"前往AI客服配置修改"→ 跳转到settings-ai-cs

- [ ] **Step 4: 验证作用域优先级**

1. 关闭某账号的账号级enabled
2. 该账号下商品auto_reply_enabled为NULL → effective应为false（账号级覆盖）
3. 单独开启该账号下某商品 → 该商品effective为true（商品级覆盖账号级）
4. 关闭全局主开关 → 所有商品effective为false（门控）

- [ ] **Step 5: 验证数据库一致性**

运行 SQL 检查：
```sql
SELECT id, title, account_id, auto_reply_enabled FROM xianyu_goods WHERE auto_reply_enabled IS NOT NULL LIMIT 10;
SELECT setting_key, config_json FROM user_business_setting WHERE setting_key IN ('ai-customer-service', 'auto-reply-account-scopes');
```
Expected: 商品级和账号级配置正确持久化

- [ ] **Step 6: 最终 Commit（如有修复）**

```bash
git add -A
git commit -m "test: 端到端联调验证通过"
```

---

## 自审清单

**Spec 覆盖检查**：
- [x] A1 默认值优化 + 恢复默认按钮 → Task 5, 11
- [x] A2 知识库大段文本 → Task 9
- [x] A3 文件上传 + AI提取 → Task 2, 6, 10
- [x] A4 实时回复预览修复 → Task 6 (errorCode), 12
- [x] B1 双列结构 → Task 14
- [x] B2 极简策略面板 → Task 14
- [x] B3 作用域切换逻辑 → Task 14
- [x] B4 移除接口调用 → Task 14 (整体替换)
- [x] C1 自动回复开关直接生效 → Task 13
- [x] C2 前置校验 → Task 13
- [x] C3 批量操作 → Task 13 (单商品) + Task 14 (批量)
- [x] D Python knowledge_base.py → Task 2
- [x] D Python auto_reply_scope.py → Task 3
- [x] D Java BusinessSettingsController 扩展 → Task 6
- [x] D Java AutoReplyScopeController → Task 7
- [x] D items.py 替换占位 → Task 4
- [x] DB 迁移 → Task 1
- [x] 前端 API 封装 → Task 8

**Placeholder 扫描**：无 TBD/TODO，所有步骤含完整代码。

**类型一致性**：
- `auto_reply_enabled` 在 Python 实体、DB、API 响应中一致（SmallInteger/TINYINT，0/1/NULL）
- `updateProductAutoReplyScope(itemId, enabled)` 在 API 和调用方一致
- `getAutoReplyScopeProducts(accountId)` 在 API 和调用方一致

**已知风险点**（实施时需验证）：
1. `ai_provider_service.generate_text_async` 方法是否存在 - Task 2 Step 2-3 已处理
2. `tenant_context.get_current_tenant_id` 是否存在 - Task 3 Step 2 已处理
3. ProductsPage 中 `row.raw.id` 字段名 - Task 13 Step 3 已注明需根据实际结构调整
4. `goToModelConfig` 跳转路径 - Task 12 Step 3 已注明需根据路由调整
5. `confirmAction` 工具函数是否已存在 - Task 11 Step 2 已注明检查方式
