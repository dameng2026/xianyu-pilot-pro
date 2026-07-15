"""
Phase 5: Final cleanup of remaining tenant_id references in route files,
services tenant_id removal, xianyu_goods_sync search removal, model addition,
and api.py router registration.
"""
import os
import re

TARGET_APP = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app'
ROUTES_DIR = os.path.join(TARGET_APP, 'api', 'v1', 'routes')
SERVICES_DIR = os.path.join(TARGET_APP, 'services')
MODELS_DIR = os.path.join(TARGET_APP, 'models')


def read(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write(path, content):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


# ============================================================
# 1. Route files: remaining tenant_id cleanup
# ============================================================

def fix_messages_py():
    """messages.py: remove remaining tenant_id references."""
    p = os.path.join(ROUTES_DIR, 'messages.py')
    c = read(p)
    # Remove "if not tenant_id:" check (line 82) - tenant_id not defined
    c = re.sub(
        r'\s*if not tenant_id:\s*\n\s*return ResultObject\.success\(\{"records": \[\], "total": 0, "pageNum": page_num, "pageSize": page_size, "pages": 0\}\)\s*\n',
        '\n',
        c,
    )
    # Remove tenant_id from get_context_messages call
    c = re.sub(
        r'get_context_messages\(\s*db,\s*tenant_id,\s*int\(account_id\),',
        'get_context_messages(\n            db, int(account_id),',
        c,
    )
    # Remove tenant_id from _save_conversation_user_info call
    c = re.sub(
        r'_save_conversation_user_info\(\s*db,\s*tenant_id,\s*int\(account_id\),\s*cid,\s*avatar,\s*nick\s*\)',
        '_save_conversation_user_info(\n                    db, int(account_id), cid, avatar, nick\n                )',
        c,
    )
    write(p, c)
    print('  messages.py: fixed')


def fix_quick_reply_py():
    """quick_reply.py: remove remaining tenant_id in params dict."""
    p = os.path.join(ROUTES_DIR, 'quick_reply.py')
    c = read(p)
    # Remove {"tenant_id": tenant_id} params - replace with empty dict
    c = re.sub(
        r'text\("SELECT COUNT\(\*\) AS cnt FROM quick_reply_template WHERE deleted = 0"\),\s*\n\s*\{"tenant_id": tenant_id\}',
        'text("SELECT COUNT(*) AS cnt FROM quick_reply_template WHERE deleted = 0")',
        c,
    )
    write(p, c)
    print('  quick_reply.py: fixed')


def fix_misc_py():
    """misc.py: remove remaining tenant_id references."""
    p = os.path.join(ROUTES_DIR, 'misc.py')
    c = read(p)
    # Remove "tenant_id = session_data.get("tenant_id")" line
    c = re.sub(
        r'\s*tenant_id\s*=\s*session_data\.get\("tenant_id"\)\s*\n',
        '\n',
        c,
    )
    # Remove "if not tenant_id:" check
    c = re.sub(
        r'\s*if not tenant_id:\s*\n\s*return \{"_error": "NO_TENANT", "message": "缺少租户信息"\}\s*\n',
        '\n',
        c,
    )
    # Remove the try/except clear_cookie_expired_state block
    c = re.sub(
        r'\s*# 扫码登录成功后 cookie_status=1，清除 Cookie 失效通知去重标记。\s*\n\s*try:\s*\n\s*from app\.services\.notify_dispatcher import clear_cookie_expired_state\s*\n\s*clear_cookie_expired_state\(tenant_id, int\(account\.id\)\)\s*\n\s*except Exception:\s*\n\s*logger\.debug\("clear_cookie_expired_state 调用异常，忽略", exc_info=True\)\s*\n',
        '\n',
        c,
    )
    # Remove tenant_id from _resolve_ws_goods_id calls
    c = re.sub(
        r'_resolve_ws_goods_id\(db,\s*tenant_id,\s*account_id,\s*ws_sid,',
        '_resolve_ws_goods_id(db, account_id, ws_sid,',
        c,
    )
    # Remove tenant_id from save_chat_message calls
    c = re.sub(
        r'save_chat_message\(db,\s*tenant_id,\s*account_id,\s*\{',
        'save_chat_message(db, account_id, {',
        c,
    )
    write(p, c)
    print('  misc.py: fixed')


def fix_items_py():
    """items.py: remove "if not tenant_raw:" checks (tenant_raw undefined)."""
    p = os.path.join(ROUTES_DIR, 'items.py')
    c = read(p)
    c = re.sub(
        r'\s*if not tenant_raw:\s*\n\s*return ResultObject\.failed\("缺少租户上下文"\)\s*\n',
        '\n',
        c,
    )
    write(p, c)
    print('  items.py: fixed')


def fix_auto_reply_scope_py():
    """auto_reply_scope.py: remove _get_tenant_id function and remaining tenant_id refs."""
    p = os.path.join(ROUTES_DIR, 'auto_reply_scope.py')
    c = read(p)
    # Remove _get_tenant_id function
    c = re.sub(
        r'\ndef _get_tenant_id\(request: Request\).*?return int\(raw\)\s*\n\s*except \(ValueError, TypeError\):\s*\n\s*return 0\s*\n',
        '\n',
        c,
        flags=re.DOTALL,
    )
    # Remove "if tenant_id <= 0:" checks
    c = re.sub(
        r'\s*if tenant_id <= 0:\s*\n\s*return ResultObject\.failed\("无效的租户ID"\)\s*\n',
        '\n',
        c,
    )
    c = re.sub(
        r'\s*if tenant_id <= 0:\s*\n\s*return ResultObject\.validate_failed\([^)]*\)\s*\n',
        '\n',
        c,
    )
    # Remove "tenantId" query parameter from function signatures
    c = re.sub(r',?\s*tenantId:\s*Optional\[int\]\s*=\s*None,?\s*\n', '\n', c)
    # Remove "tenant_id = _get_tenant_id(request)" assignments
    c = re.sub(r'\s*tenant_id\s*=\s*_get_tenant_id\(request\)\s*\n', '\n', c)
    # Remove tenant_id from SQL params: {"tid": tenant_id, ...}
    c = re.sub(r'\{"tid":\s*tenant_id,\s*"key":\s*([^}]+)\}', r'{\1}', c)
    c = re.sub(r'\{"tid":\s*tenant_id,\s*"key":\s*([^}]+),\s*"json":\s*([^}]+)\}', r'{"key": \1, "json": \2}', c)
    c = re.sub(r'\{"tid":\s*tenant_id\}', '{}', c)
    # Remove "AND tenant_id = :tid" from SQL
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tid\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tid\s*\n', '\n', c, flags=re.IGNORECASE)
    # Remove tenant_id from params dict
    c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r'\s*params:\s*Dict\[str,\s*Any\]\s*=\s*\{\s*"tenant_id":\s*tenant_id\s*\}', 'params: Dict[str, Any] = {}', c)
    # Remove the comment about tenant_id
    c = re.sub(r'\s*# 唯一键为 \(tenant_id, user_id, setting_key\).*?\n', '\n', c)
    write(p, c)
    print('  auto_reply_scope.py: fixed')


def fix_feishu_py():
    """feishu.py: simplify encrypted event handling and fix feishu_config_check."""
    p = os.path.join(ROUTES_DIR, 'feishu.py')
    c = read(p)
    # Replace the entire encrypted event block (lines 71-112) with a simplified version
    # that loads config from default tenant 1
    old_encrypted_block = '''        # === 处理加密事件 ===
        if "encrypt" in body:
            # 需要从所有租户配置中查找匹配的 encrypt_key
            # 简化处理：遍历可能的 tenant_id（性能可接受，事件回调量很小）
            from sqlalchemy import text
            from app.core.database import async_session
            async with async_session() as db:
                rows = (await db.execute(
                    text(
                        "SELECT tenant_id, config_json FROM user_notification_setting "
                        "WHERE deleted = 0"
                    )
                )).mappings().all()

            decrypted = None
            tenant_id_found = None
            for row in rows:
                try:
                    config = row["config_json"]
                    if isinstance(config, str):
                        config = json.loads(config)
                    channels = config.get("channels") or []
                    for ch in channels:
                        if ch.get("type") == "feishu_app" and ch.get("enabled"):
                            encrypt_key = ch.get("encryptKey") or ch.get("encrypt_key") or ""
                            if encrypt_key:
                                try:
                                    decrypted = decrypt_encrypted_event(encrypt_key, body["encrypt"])
                                    tenant_id_found = int(row["tenant_id"])
                                    break
                                except Exception:
                                    continue
                    if decrypted:
                        break
                except Exception:
                    continue

            if not decrypted:
                logger.warning("飞书事件加密但无法解密：未找到匹配的 encrypt_key")
                return JSONResponse(status_code=400, content={"error": "decrypt failed"})
            body = decrypted
            _found
        else:
            # 未加密：从 header.tenant_key 或 app_id 推断 tenant_id
            tenant_key = body.get("header", {}).get("tenant_key", "")
            tenant_id = _resolve_tenant_id_from_tenant_key(tenant_key, body)'''
    new_encrypted_block = '''        # === 处理加密事件 ===
        # 单租户模式：直接使用默认租户 ID 1 加载配置
        tenant_id = 1
        if "encrypt" in body:
            config = await _load_feishu_app_config(tenant_id)
            if not config:
                logger.warning("飞书事件回调但租户未配置自建应用: tenant_id=%d", tenant_id)
                return JSONResponse(status_code=200, content={"code": 0, "msg": "not configured"})
            encrypt_key = config.get("encryptKey") or config.get("encrypt_key") or ""
            if not encrypt_key:
                logger.warning("飞书事件加密但未配置 encrypt_key")
                return JSONResponse(status_code=400, content={"error": "decrypt failed"})
            try:
                body = decrypt_encrypted_event(encrypt_key, body["encrypt"])
            except Exception:
                logger.warning("飞书事件加密但无法解密")
                return JSONResponse(status_code=400, content={"error": "decrypt failed"})'''
    c = c.replace(old_encrypted_block, new_encrypted_block)

    # Remove the now-redundant "if tenant_id is None:" check
    c = re.sub(
        r'\s*if tenant_id is None:\s*\n\s*logger\.warning\("飞书事件无法确定 tenant_id: tenant_key=%s", tenant_key\)\s*\n\s*# 仍然返回 200 避免飞书重试\s*\n\s*return JSONResponse\(status_code=200, content=\{"code": 0, "msg": "tenant not found"\}\)\s*\n',
        '\n',
        c,
    )

    # Fix feishu_config_check: replace tenant_id with 1
    c = c.replace(
        '    config = await _load_feishu_app_config(tenant_id)\n    if not config:\n        return ResultObject.failed("未配置飞书自建应用")',
        '    config = await _load_feishu_app_config(1)\n    if not config:\n        return ResultObject.failed("未配置飞书自建应用")',
    )
    write(p, c)
    print('  feishu.py: fixed')


# ============================================================
# 2. Services: remove tenant_id from function signatures and queries
# ============================================================

def fix_ws_storage_py():
    """ws_storage.py: remove tenant_id from function signatures and SQL queries."""
    p = os.path.join(SERVICES_DIR, 'ws_storage.py')
    c = read(p)
    # Remove tenant_id from function signatures
    c = re.sub(r'async def save_chat_message\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,\s*account_id:\s*int,',
               'async def save_chat_message(\n    db: AsyncSession,\n    account_id: int,', c)
    c = re.sub(r'async def get_online_conversations\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,',
               'async def get_online_conversations(\n    db: AsyncSession,', c)
    c = re.sub(r'async def get_online_conversations_paged\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,',
               'async def get_online_conversations_paged(\n    db: AsyncSession,', c)
    c = re.sub(r'async def get_context_messages\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,',
               'async def get_context_messages(\n    db: AsyncSession,', c)
    c = re.sub(r'async def _save_conversation_user_info\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,',
               'async def _save_conversation_user_info(\n    db: AsyncSession,', c)
    # Remove tenant_id from SQL queries: "AND tenant_id = :tenant_id"
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+xm\.tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+c\.tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+msg\.tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+c\.tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    # Remove "tenant_id = :tenant_id" from SET clauses
    c = re.sub(r'tenant_id\s*=\s*:tenant_id,\s*', '', c)
    # Remove tenant_id from INSERT statements
    c = re.sub(r'INSERT INTO xianyu_chat_message\s*\(\s*tenant_id,\s*', 'INSERT INTO xianyu_chat_message (', c)
    c = re.sub(r'INSERT INTO xianyu_conversation\s*\(\s*tenant_id,\s*', 'INSERT INTO xianyu_conversation (', c)
    # Remove tenant_id from VALUES
    c = re.sub(r'VALUES\s*\(:tenant_id,\s*', 'VALUES (', c)
    # Remove "tenant_id": tenant_id from params
    c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r'\s*"tenant_id":\s*int\([^)]*\),?\s*\n', '\n', c)
    # Remove tenant_id from ON DUPLICATE KEY UPDATE
    c = re.sub(r'tenant_id=VALUES\(tenant_id\),\s*', '', c)
    # Remove remaining "tenant_id" column references in SELECT
    c = re.sub(r'select\(\s*XianyuChatMessage\.tenant_id,\s*', 'select(', c, flags=re.IGNORECASE)
    c = re.sub(r'XianyuChatMessage\.tenant_id,\s*', '', c)
    c = re.sub(r'XianyuConversation\.tenant_id,\s*', '', c)
    c = re.sub(r'XianyuMessage\.tenant_id,\s*', '', c)
    # Remove .where(Model.tenant_id == tenant_id) clauses
    c = re.sub(r'\.where\(\s*XianyuChatMessage\.tenant_id\s*==\s*tenant_id,\s*', '.where(', c)
    c = re.sub(r'\.where\(\s*XianyuConversation\.tenant_id\s*==\s*tenant_id,\s*', '.where(', c)
    c = re.sub(r'\.where\(\s*XianyuMessage\.tenant_id\s*==\s*tenant_id,\s*', '.where(', c)
    # Remove standalone "XianyuChatMessage.tenant_id == tenant_id" from where chains
    c = re.sub(r'XianyuChatMessage\.tenant_id\s*==\s*tenant_id,\s*', '', c)
    c = re.sub(r'XianyuConversation\.tenant_id\s*==\s*tenant_id,\s*', '', c)
    c = re.sub(r'XianyuMessage\.tenant_id\s*==\s*tenant_id,\s*', '', c)
    # Remove tenant_id from logging statements
    c = re.sub(r'"tenant_id=%s,\s*', '"', c)
    c = re.sub(r'",\s*tenant_id,\s*', '", ', c)
    c = re.sub(r'",\s*tenant_id\)', '")', c)
    c = re.sub(r',\s*tenant_id=%s,\s*', ', ', c)
    c = re.sub(r',\s*tenant_id\)', ')', c)
    c = re.sub(r'tenant_id=%s,\s*', '', c)
    write(p, c)
    print('  ws_storage.py: fixed')


def fix_ws_client_py():
    """ws_client.py: remove tenant_id references."""
    p = os.path.join(SERVICES_DIR, 'ws_client.py')
    c = read(p)
    # Remove tenant_id from function signatures
    c = re.sub(r',\s*tenant_id:\s*int\s*=\s*0', '', c)
    c = re.sub(r',\s*tenant_id:\s*int', '', c)
    c = re.sub(r',\s*tenant_id:\s*Optional\[int\]\s*=\s*None', '', c)
    # Remove tenant_id from self.tenant_id attributes (replace with default 0)
    c = re.sub(r'self\.tenant_id\s*=\s*tenant_id\s*\n', '', c)
    # Remove tenant_id from logging
    c = re.sub(r'"tenant_id=%s,\s*', '"', c)
    c = re.sub(r'",\s*tenant_id,\s*', '", ', c)
    c = re.sub(r'",\s*tenant_id\)', '")', c)
    c = re.sub(r',\s*tenant_id=%s,\s*', ', ', c)
    c = re.sub(r',\s*tenant_id\)', ')', c)
    c = re.sub(r'tenant_id=%s,\s*', '', c)
    # Remove tenant_id from function calls
    c = re.sub(r',\s*tenant_id=tenant_id', '', c)
    c = re.sub(r',\s*tenant_id=\d+', '', c)
    c = re.sub(r',\s*tenant_id', '', c)
    # Remove "self.tenant_id" references
    c = re.sub(r',\s*self\.tenant_id', '', c)
    c = re.sub(r'self\.tenant_id,\s*', '', c)
    write(p, c)
    print('  ws_client.py: fixed')


def fix_ws_startup_py():
    """ws_startup.py: remove tenant_id references."""
    p = os.path.join(SERVICES_DIR, 'ws_startup.py')
    c = read(p)
    # Remove tenant_id from function signatures
    c = re.sub(r',\s*tenant_id:\s*int\s*=\s*0', '', c)
    c = re.sub(r',\s*tenant_id:\s*int', '', c)
    c = re.sub(r',\s*tenant_id:\s*Optional\[int\]\s*=\s*None', '', c)
    # Remove tenant_id from SQL queries
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*AND\s+a\.tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    # Remove tenant_id from params
    c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    c = re.sub(r'\s*"tenant_id":\s*int\([^)]*\),?\s*\n', '\n', c)
    # Remove tenant_id from logging
    c = re.sub(r'"tenant_id=%s,\s*', '"', c)
    c = re.sub(r'",\s*tenant_id,\s*', '", ', c)
    c = re.sub(r'",\s*tenant_id\)', '")', c)
    c = re.sub(r',\s*tenant_id=%s,\s*', ', ', c)
    c = re.sub(r',\s*tenant_id\)', ')', c)
    c = re.sub(r'tenant_id=%s,\s*', '', c)
    # Remove tenant_id from function calls
    c = re.sub(r',\s*tenant_id=tenant_id', '', c)
    c = re.sub(r',\s*tenant_id', '', c)
    write(p, c)
    print('  ws_startup.py: fixed')


def fix_captcha_solver_py():
    """captcha_solver.py: remove tenant_id references."""
    p = os.path.join(SERVICES_DIR, 'captcha_solver.py')
    c = read(p)
    # Remove tenant_id from function signatures
    c = re.sub(r',\s*tenant_id:\s*int\s*=\s*0', '', c)
    c = re.sub(r',\s*tenant_id:\s*int', '', c)
    c = re.sub(r',\s*tenant_id:\s*Optional\[int\]\s*=\s*None', '', c)
    # Remove tenant_id from SQL queries
    c = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', c, flags=re.IGNORECASE)
    # Remove tenant_id from params
    c = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', c)
    # Remove tenant_id from logging
    c = re.sub(r'"tenant_id=%s,\s*', '"', c)
    c = re.sub(r'",\s*tenant_id,\s*', '", ', c)
    c = re.sub(r'",\s*tenant_id\)', '")', c)
    c = re.sub(r',\s*tenant_id=%s,\s*', ', ', c)
    c = re.sub(r',\s*tenant_id\)', ')', c)
    c = re.sub(r'tenant_id=%s,\s*', '', c)
    # Remove tenant_id from function calls
    c = re.sub(r',\s*tenant_id=tenant_id', '', c)
    c = re.sub(r',\s*tenant_id', '', c)
    write(p, c)
    print('  captcha_solver.py: fixed')


# ============================================================
# 3. xianyu_goods_sync.py: remove SEARCH_MTOP_API and _normalize_mtop_search_item
# ============================================================

def fix_xianyu_goods_sync_py():
    """Remove search-related functions from xianyu_goods_sync.py."""
    p = os.path.join(SERVICES_DIR, 'xianyu_goods_sync.py')
    c = read(p)
    # Remove SEARCH_MTOP_API constant
    c = re.sub(
        r'\n# 搜索 API 常量（用于商品获取节点和商机发掘页面）\s*\nSEARCH_MTOP_API\s*=\s*"mtop\.taobao\.idlemtopsearch\.pc\.search"\s*\n',
        '\n',
        c,
    )
    # Remove _normalize_mtop_search_item function (it's a large function with docstring)
    c = re.sub(
        r'\ndef _normalize_mtop_search_item\(raw: dict\)-> dict:.*?(?=\n\n\nasync def |\n\nasync def |\n\nclass |\n\ndef |\Z)',
        '\n',
        c,
        flags=re.DOTALL,
    )
    # Also handle the case where the return type annotation has spaces
    c = re.sub(
        r'\ndef _normalize_mtop_search_item\(raw: dict\) -> dict:.*?(?=\n\n\nasync def |\n\nasync def |\n\nclass |\n\ndef |\Z)',
        '\n',
        c,
        flags=re.DOTALL,
    )
    write(p, c)
    print('  xianyu_goods_sync.py: removed search functions')


# ============================================================
# 4. Add XianyuGoodsSyncTask model to entities.py
# ============================================================

def add_sync_task_model():
    """Add XianyuGoodsSyncTask model to entities.py (without tenant_id)."""
    p = os.path.join(MODELS_DIR, 'entities.py')
    c = read(p)
    if 'class XianyuGoodsSyncTask' in c:
        print('  entities.py: XianyuGoodsSyncTask already exists, skipping')
        return
    # Insert after XianyuGoods class (before XianyuTradeOrder)
    model_def = '''

class XianyuGoodsSyncTask(Base):
    """商品同步任务表（单租户精简版，无 tenant_id）。"""
    __tablename__ = "xianyu_goods_sync_task"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sync_id = Column(String(80), nullable=False, unique=True, comment="同步任务ID")
    account_id = Column(BigInteger, nullable=False)
    status = Column(String(30), nullable=False, default="queued", comment="queued/running/completed/failed")
    progress = Column(Integer, default=0)
    total_count = Column(Integer, default=0)
    new_count = Column(Integer, default=0)
    updated_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    off_shelf_count = Column(Integer, default=0)
    detail_synced_count = Column(Integer, default=0)
    duration_seconds = Column(Float, default=0)
    error_message = Column(Text, nullable=True)
    started_time = Column(DateTime, nullable=True)
    finished_time = Column(DateTime, nullable=True)
    deleted = Column(SmallInteger, default=0)
    created_time = Column(DateTime, default=func.now())
    updated_time = Column(DateTime, default=func.now(), onupdate=func.now())


'''
    # Insert before "class XianyuTradeOrder"
    c = c.replace('\n\nclass XianyuTradeOrder(Base):', model_def + 'class XianyuTradeOrder(Base):')
    write(p, c)
    print('  entities.py: added XianyuGoodsSyncTask model')


# ============================================================
# 5. Update api.py to register all migrated routers
# ============================================================

def update_api_py():
    """Update api.py to register all migrated routers."""
    p = os.path.join(TARGET_APP, 'api', 'v1', 'api.py')
    content = '''"""
API 路由聚合
============
注册所有业务路由模块到 api_router。
单租户精简版：不包含 workflow/opportunity/ai_transaction 等模块。
"""
from fastapi import APIRouter

from .routes import (
    account,
    auto_category,
    auto_reply_scope,
    captcha,
    dashboard,
    feishu,
    internal,
    items,
    kami,
    login,
    messages,
    misc,
    quick_reply,
    restful,
    sse,
    system,
)

api_router = APIRouter()

# 账号与登录
api_router.include_router(account.router)
api_router.include_router(login.router)

# 商品与同步
api_router.include_router(items.router)
api_router.include_router(auto_category.router)

# 消息与会话
api_router.include_router(messages.router)
api_router.include_router(misc.router)

# 卡密与发货
api_router.include_router(kami.router)
api_router.include_router(restful.router)

# 系统配置
api_router.include_router(system.router)
api_router.include_router(dashboard.router)

# 自动回复
api_router.include_router(auto_reply_scope.router)
api_router.include_router(quick_reply.router)

# 验证码与滑块
api_router.include_router(captcha.router)

# 飞书
api_router.include_router(feishu.router)

# 内部接口
api_router.include_router(internal.router)

# SSE 推流
api_router.include_router(sse.router)
'''
    write(p, content)
    print('  api.py: updated with all routers')


def main():
    print('=== Phase 5: Final cleanup ===')
    print('\n[1/5] Route files cleanup:')
    fix_messages_py()
    fix_quick_reply_py()
    fix_misc_py()
    fix_items_py()
    fix_auto_reply_scope_py()
    fix_feishu_py()

    print('\n[2/5] Services cleanup:')
    fix_ws_storage_py()
    fix_ws_client_py()
    fix_ws_startup_py()
    fix_captcha_solver_py()

    print('\n[3/5] xianyu_goods_sync.py search removal:')
    fix_xianyu_goods_sync_py()

    print('\n[4/5] Add XianyuGoodsSyncTask model:')
    add_sync_task_model()

    print('\n[5/5] Update api.py:')
    update_api_py()

    print('\n=== Phase 5 complete ===')


if __name__ == '__main__':
    main()
