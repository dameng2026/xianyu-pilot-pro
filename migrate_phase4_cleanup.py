"""
Phase 4: Comprehensive tenant_id cleanup across all route files.
Handles function signatures, SQL queries, validation checks, logging, and dict literals.
"""
import os
import re

ROUTES_DIR = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes'


def read_file(name):
    path = os.path.join(ROUTES_DIR, name)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def write_file(name, content):
    path = os.path.join(ROUTES_DIR, name)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def cleanup_account():
    """account.py: remove tenant_id from clear_cookie_expired_state call."""
    content = read_file('account.py')
    # Remove the try/except block that calls clear_cookie_expired_state
    content = re.sub(
        r'\s*try:\s*\n\s*from app\.services\.notify_dispatcher import clear_cookie_expired_state\s*\n\s*clear_cookie_expired_state\(tenant_id, int\(account_id\)\)\s*\n\s*except Exception:\s*\n\s*logger\.debug\("clear_cookie_expired_state 调用异常，忽略", exc_info=True\)\s*\n',
        '\n',
        content,
    )
    write_file('account.py', content)
    print('  account.py: cleaned')


def cleanup_auto_category():
    """auto_category.py: remove _require_tenant and tenant_id from _get_account_cookie."""
    content = read_file('auto_category.py')
    # Remove _require_tenant function
    content = re.sub(
        r'def _require_tenant\(current_user[^)]*\)[^}]*?return int\(tenant_id\)\s*\n',
        '',
        content,
        flags=re.DOTALL,
    )
    # Remove tenant_id = _require_tenant(current_user) lines
    content = re.sub(r'\s*tenant_id\s*=\s*_require_tenant\(current_user\)\s*\n', '\n', content)
    # Remove tenant_id from _get_account_cookie signature
    content = content.replace(
        'async def _get_account_cookie(db: AsyncSession, account_id: int, tenant_id: int)',
        'async def _get_account_cookie(db: AsyncSession, account_id: int)'
    )
    # Remove tenant_id from _get_account_cookie call sites
    content = re.sub(r'_get_account_cookie\(db,\s*account_id,\s*tenant_id\)', '_get_account_cookie(db, account_id)', content)
    # Remove tenant_id conditions in SQL: "AND a.tenant_id = :tenant_id"
    content = re.sub(r'\s*AND\s+a\.tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+a\.tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+a\.tenant_id\s*=\s*:tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    # Remove tenant_id from params
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    write_file('auto_category.py', content)
    print('  auto_category.py: cleaned')


def cleanup_auto_reply_scope():
    """auto_reply_scope.py: remove _get_tenant_id and all tenant_id from queries."""
    content = read_file('auto_reply_scope.py')
    # Remove _get_tenant_id function
    content = re.sub(
        r'def _get_tenant_id\(request: Request\).*?return tenant_id\s*\n',
        '',
        content,
        flags=re.DOTALL,
    )
    # Remove tenant_id = _get_tenant_id(request) lines
    content = re.sub(r'\s*tenant_id\s*=\s*_get_tenant_id\(request\)\s*\n', '\n', content)
    # Remove "if tenant_id <= 0:" checks (and the following return)
    content = re.sub(
        r'\s*if tenant_id <= 0:\s*\n\s*return ResultObject\.validate_failed\([^)]*\)\s*\n',
        '\n',
        content,
    )
    # Remove tenant_id from function signatures
    content = re.sub(r',\s*tenant_id:\s*int\)', ')', content)
    content = re.sub(r'\(db:\s*AsyncSession,\s*tenant_id:\s*int\)', '(db: AsyncSession)', content)
    content = re.sub(r'\(db:\s*AsyncSession,\s*tenant_id:\s*int,\s*', '(db: AsyncSession, ', content)
    # Remove tenant_id from function calls
    content = re.sub(r'_load_account_scopes\(db,\s*tenant_id\)', '_load_account_scopes(db)', content)
    content = re.sub(r'_save_account_scopes\(db,\s*tenant_id,\s*', '_save_account_scopes(db, ', content)
    content = re.sub(r'_load_global_enabled\(db,\s*tenant_id\)', '_load_global_enabled(db)', content)
    content = re.sub(r'_load_goods_rows\(db,\s*tenant_id,\s*', '_load_goods_rows(db, ', content)
    # Remove tenant_id from SQL queries
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tid\s+AND', 'WHERE', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tid', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tid\s*\n', '\n', content, flags=re.IGNORECASE)
    # Remove tenant_id from INSERT statements
    content = re.sub(r'INSERT INTO user_business_setting\(tenant_id,\s*user_id,\s*', 'INSERT INTO user_business_setting(user_id, ', content)
    content = re.sub(r'VALUES\s*\(:tid,\s*0,\s*', 'VALUES (0, ', content)
    content = re.sub(r'VALUES\s*\(:tid,\s*:uid,\s*', 'VALUES (:uid, ', content)
    # Remove "tid": tenant_id from params
    content = re.sub(r'\s*"tid":\s*tenant_id,?\s*\n', '\n', content)
    # Remove tenant_id from params dict
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    # Remove ON DUPLICATE KEY UPDATE tenant_id=VALUES(tenant_id),
    content = re.sub(r'tenant_id=VALUES\(tenant_id\),\s*', '', content)
    write_file('auto_reply_scope.py', content)
    print('  auto_reply_scope.py: cleaned')


def cleanup_captcha():
    """captcha.py: remove tenant_id from handle_captcha endpoint."""
    content = read_file('captcha.py')
    # Remove tenant_id line and validation
    content = re.sub(
        r'\s*tenant_id\s*=\s*int\(data\.get\("tenantId"\) or current_user\.get\("tenant_id"\) or 0\)\s*\n',
        '\n',
        content,
    )
    content = re.sub(
        r'\s*if not account_id or not tenant_id:\s*\n\s*return ResultObject\.validate_failed\("accountId 和 tenantId 不能为空"\)\s*\n',
        '\n        if not account_id:\n            return ResultObject.validate_failed("accountId 不能为空")\n',
        content,
    )
    # Remove tenant_id=tenant_id from handle_captcha_for_account call
    content = re.sub(r',\s*tenant_id\s*=\s*tenant_id', '', content)
    # Remove the "tenantId": 1 from docstring/comment
    content = re.sub(r'\s*"tenantId":\s*1,\s*#.*\n', '\n', content)
    write_file('captcha.py', content)
    print('  captcha.py: cleaned')


def cleanup_dashboard():
    """dashboard.py: remove tenant_id from _get_delivery_stats."""
    content = read_file('dashboard.py')
    # Remove tenant_id from function signature
    content = content.replace(
        'async def _get_delivery_stats(db: AsyncSession, tenant_id: int) -> dict:',
        'async def _get_delivery_stats(db: AsyncSession) -> dict:'
    )
    # Remove tenant_id from call sites
    content = re.sub(r'_get_delivery_stats\(db,\s*tenant_id\)', '_get_delivery_stats(db)', content)
    # Remove tenant_id conditions in SQL
    content = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    # Remove tenant_id from params
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    write_file('dashboard.py', content)
    print('  dashboard.py: cleaned')


def cleanup_items():
    """items.py: remove remaining tenant_id from logging, validation, and is_syncing."""
    content = read_file('items.py')
    # Remove tenant_id from logging
    content = re.sub(
        r'logger\.info\("商品同步已启动: account_id=%d, sync_id=%s, tenant_id=%s", account_id, sync_id, tenant_id\)',
        'logger.info("商品同步已启动: account_id=%d, sync_id=%s", account_id, sync_id)',
        content,
    )
    content = re.sub(
        r'logger\.info\("本地删除商品: tenant_id=%s, goods_id=%s", tenant_id, xy_goods_id\)',
        'logger.info("本地删除商品: goods_id=%s", xy_goods_id)',
        content,
    )
    # Remove tenant_id from validation checks
    content = re.sub(r'if not tenant_id or not account_id or not (xy_goods_id|item_ids):',
                     lambda m: f'if not account_id or not {m.group(1)}:', content)
    # Remove tenant_id params from is_syncing
    content = re.sub(r'\s*tenantId:\s*int\s*\|\s*None\s*=\s*None,\s*\n', '\n', content)
    content = re.sub(r'\s*tenant_id:\s*int\s*\|\s*None\s*=\s*None,\s*\n', '\n', content)
    # Remove tenant_value logic
    content = re.sub(r'\s*tenant_value\s*=\s*tenantId or tenant_id\s*\n', '\n', content)
    # Remove XianyuGoodsSyncTask.tenant_id query
    content = re.sub(r'\s*if tenant_value:\s*\n\s*query\s*=\s*query\.where\(XianyuGoodsSyncTask\.tenant_id\s*==\s*int\(tenant_value\)\)\s*\n', '\n', content)
    # Remove "tenant_id=%s" from other logging
    content = re.sub(r',\s*tenant_id=%s,\s*', ', ', content)
    content = re.sub(r'tenant_id=%s,\s*', '', content)
    write_file('items.py', content)
    print('  items.py: cleaned')


def cleanup_kami():
    """kami.py: remove tenant_id=current_user.get("tenant_id") from constructor calls."""
    content = read_file('kami.py')
    content = re.sub(r',\s*tenant_id\s*=\s*current_user\.get\(\s*["\']tenant_id["\']\s*\)', '', content)
    content = re.sub(r'tenant_id\s*=\s*current_user\.get\(\s*["\']tenant_id["\']\s*\),\s*', '', content)
    write_file('kami.py', content)
    print('  kami.py: cleaned')


def cleanup_messages():
    """messages.py: remove tenant_id from SQL queries and function signatures."""
    content = read_file('messages.py')
    # Remove tenant_id = current_user.get("tenant_id") or req.tenant_id
    content = re.sub(
        r'\s*tenant_id\s*=\s*current_user\.get\("tenant_id"\)\s*or\s*req\.tenant_id\s*\n',
        '\n',
        content,
    )
    content = re.sub(
        r'\s*tenant_id\s*=\s*current_user\.get\("tenant_id"\)\s*or\s*req\.get\("tenantId"\)\s*\n',
        '\n',
        content,
    )
    # Remove if not tenant_id checks
    content = re.sub(r'\s*if not tenant_id:\s*\n\s*return ResultObject\.validate_failed\([^)]*\)\s*\n', '\n', content)
    # Remove tenant_id from where_sql
    content = re.sub(r'where_sql\s*=\s*\["tenant_id\s*=\s*:tenant_id",\s*"deleted\s*=\s*0"\]',
                     'where_sql = ["deleted = 0"]', content)
    content = re.sub(r'params\s*=\s*\{\s*"tenant_id":\s*tenant_id\s*\}', 'params = {}', content)
    # Remove tenant_id from logging
    content = re.sub(r'"message_context: tenant_id=%s account_id=%s s_id=%s user_id=%s peer_user_id=%s",\s*\n\s*tenant_id,\s*account_id,',
                     '"message_context: account_id=%s s_id=%s user_id=%s peer_user_id=%s",\n                     account_id,', content)
    # Remove tenant_id from validation
    content = re.sub(r'if not tenant_id or not account_id or', 'if not account_id or', content)
    # Remove tenant_id from function calls
    content = re.sub(r'\(db,\s*tenant_id,\s*int\(account_id\),', '(db, int(account_id),', content)
    content = re.sub(r'\(db,\s*tenant_id,\s*int\(account_id\),\s*cid,\s*avatar,\s*nick\)',
                     '(db, int(account_id), cid, avatar, nick)', content)
    # Remove tenant_id from query params
    content = re.sub(r'tenant_id:\s*int\s*=\s*Query\(None,\s*alias="tenantId"\),?\s*\n', '', content)
    # Remove "or current_user.get("tenant_id")"
    content = re.sub(r'\s*or current_user\.get\("tenant_id"\)', '', content)
    # Remove tenant_id from online_conversations logging
    content = re.sub(
        r'"online_conversations: xianyuAccountId=%s cursor=%s pageSize=%s limit=%s tenantId=%s",\s*\n\s*xianyu_account_id, cursor, page_size, limit, tenant_id,',
        '"online_conversations: xianyuAccountId=%s cursor=%s pageSize=%s limit=%s",\n                     xianyu_account_id, cursor, page_size, limit,',
        content,
    )
    # Remove "if tenant_id is None or" checks
    content = re.sub(r'if tenant_id is None or ', 'if ', content)
    # Remove tenant_id from SQL: "AND tenant_id = :tenant_id"
    content = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    # Remove tenant_id from params
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    write_file('messages.py', content)
    print('  messages.py: cleaned')


def cleanup_misc():
    """misc.py: remove tenant_id from WS credential queries and function signatures."""
    content = read_file('misc.py')
    # Remove tenant_id from function signatures
    content = re.sub(r'async def _load_ws_credentials\(db:\s*AsyncSession,\s*tenant_id:\s*int,\s*account_id:\s*int\)',
                     'async def _load_ws_credentials(db: AsyncSession, account_id: int)', content)
    content = re.sub(r'async def _restart_ws_client_from_db\(db:\s*AsyncSession,\s*tenant_id:\s*int,\s*account_id:\s*int\)',
                     'async def _restart_ws_client_from_db(db: AsyncSession, account_id: int)', content)
    content = re.sub(r'async def _resolve_ws_sid\(db:\s*AsyncSession,\s*tenant_id:\s*int,\s*account_id:\s*int,\s*raw_cid:\s*object\)',
                     'async def _resolve_ws_sid(db: AsyncSession, account_id: int, raw_cid: object)', content)
    content = re.sub(r'async def _resolve_ws_peer_id\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,\s*',
                     'async def _resolve_ws_peer_id(\n    db: AsyncSession, ', content)
    content = re.sub(r'async def _resolve_outbound_image_url\(\s*db:\s*AsyncSession,\s*tenant_id:\s*int,\s*',
                     'async def _resolve_outbound_image_url(\n    db: AsyncSession, ', content)
    content = re.sub(r'def _schedule_ws_start\(account_id:\s*int,\s*tenant_id:\s*int\)',
                     'def _schedule_ws_start(account_id: int)', content)
    content = re.sub(r'async def _do_start_ws\(account_id:\s*int,\s*tenant_id:\s*int\)',
                     'async def _do_start_ws(account_id: int)', content)
    # Remove tenant_id from call sites
    content = re.sub(r'_load_ws_credentials\(db,\s*tenant_id,\s*account_id\)', '_load_ws_credentials(db, account_id)', content)
    content = re.sub(r'_restart_ws_client_from_db\(db,\s*tenant_id,\s*account_id\)', '_restart_ws_client_from_db(db, account_id)', content)
    content = re.sub(r'_resolve_ws_sid\(db,\s*tenant_id,\s*int\(account_id\)', '_resolve_ws_sid(db, int(account_id)', content)
    content = re.sub(r'_resolve_ws_sid\(db,\s*tenant_id,\s*account_id', '_resolve_ws_sid(db, account_id', content)
    content = re.sub(r'_resolve_ws_peer_id\(\s*db,\s*tenant_id,\s*', '_resolve_ws_peer_id(db, ', content)
    content = re.sub(r'_resolve_outbound_image_url\(\s*db,\s*tenant_id,\s*', '_resolve_outbound_image_url(db, ', content)
    content = re.sub(r'_schedule_ws_start\(account_id,\s*tenant_id\)', '_schedule_ws_start(account_id)', content)
    content = re.sub(r'_do_start_ws\(account_id,\s*tenant_id\)', '_do_start_ws(account_id)', content)
    # Remove tenant_id from logging
    content = re.sub(r'"QR 后调度 WS 启动: accountId=%d tenantId=%d", account_id, tenant_id',
                     '"QR 后调度 WS 启动: accountId=%d", account_id', content)
    # Remove "tenantId": tenant_id from dicts
    content = re.sub(r'\s*"tenantId":\s*tenant_id,?\s*\n', '\n', content)
    # Remove tenant_id from SQL queries
    content = re.sub(r'\s*AND\s+a\.tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*AND\s+a\.tenant_id\s*=\s*auth\.tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*ON\s+auth\.account_id\s*=\s*a\.id\s*AND\s+auth\.tenant_id\s*=\s*a\.tenant_id',
                     'ON auth.account_id = a.id', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*AND\s+c\.tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'WHERE\s+c\.tenant_id\s*=\s*:tenant_id\s+AND\s+c\.account_id\s*=\s*:account_id',
                     'WHERE c.account_id = :account_id', content, flags=re.IGNORECASE)
    content = re.sub(r'WHERE\s+xm\.tenant_id\s*=\s*c\.tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+a\.tenant_id\s*=\s*:tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    # Remove tenant_id from params
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    # Remove loop.create_task(_do_start_ws(account_id, tenant_id))
    content = re.sub(r'_do_start_ws\(account_id,\s*tenant_id\)', '_do_start_ws(account_id)', content)
    # Remove _asyncio.run(_do_start_ws(account_id, tenant_id))
    content = re.sub(r'_do_start_ws\(account_id,\s*tenant_id\)', '_do_start_ws(account_id)', content)
    # Remove remaining tenant_id references in WS functions
    content = re.sub(r',\s*tenant_id: int,', ',', content)
    write_file('misc.py', content)
    print('  misc.py: cleaned')


def cleanup_quick_reply():
    """quick_reply.py: remove _tenant_account_from_request and tenant_id from SQL."""
    content = read_file('quick_reply.py')
    # Replace _tenant_account_from_request with just account_id extraction
    content = re.sub(
        r'def _tenant_account_from_request\(request: Request\).*?return tenant_id, account_id\s*\n',
        '',
        content,
        flags=re.DOTALL,
    )
    # Remove tenant_id, account_id = _tenant_account_from_request(request)
    content = re.sub(r'tenant_id,\s*account_id\s*=\s*_tenant_account_from_request\(request\)',
                     'account_id = _account_id_from_request(request)', content)
    content = re.sub(r'tenant_id,\s*_\s*=\s*_tenant_account_from_request\(request\)',
                     'pass  # account_id not needed here', content)
    # Remove tenant_id from INSERT statements
    content = re.sub(r'INSERT INTO quick_reply_template \(tenant_id,\s*account_id,', 'INSERT INTO quick_reply_template (account_id,', content)
    content = re.sub(r'VALUES\s*\(:tenant_id,\s*:account_id,', 'VALUES (:account_id,', content)
    # Remove tenant_id from SELECT WHERE
    content = re.sub(r'\s*AND\s+tenant_id\s*=\s*:tenant_id', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s+AND', 'WHERE', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*WHERE\s+tenant_id\s*=\s*:tenant_id\s*\n', '\n', content, flags=re.IGNORECASE)
    # Remove tenant_id from params
    content = re.sub(r'\s*"tenant_id":\s*tenant_id,?\s*\n', '\n', content)
    # Add a simple _account_id_from_request function if needed
    if '_account_id_from_request' in content and 'def _account_id_from_request' not in content:
        content = content.replace(
            'router = APIRouter()',
            'router = APIRouter()\n\n\ndef _account_id_from_request(request: Request) -> int:\n    """从请求中提取 account_id。"""\n    return int(request.headers.get("X-Account-Id", "0") or "0")\n',
        )
    write_file('quick_reply.py', content)
    print('  quick_reply.py: cleaned')


def cleanup_restful():
    """restful.py: remove tenant_id from JOIN condition."""
    content = read_file('restful.py')
    # Remove the JOIN ON tenant_id condition
    content = re.sub(
        r'\.outerjoin\(\s*XianyuAccountAuth,\s*\([^)]*XianyuAccountAuth\.tenant_id\s*==\s*XianyuAccount\.tenant_id[^)]*\),?\s*\)',
        '.outerjoin(XianyuAccountAuth, XianyuAccountAuth.account_id == XianyuAccount.id)',
        content,
    )
    # Remove the standalone tenant_id JOIN condition line
    content = re.sub(r'\s*&\s*\(XianyuAccountAuth\.tenant_id\s*==\s*XianyuAccount\.tenant_id\),?\s*\n', '\n', content)
    write_file('restful.py', content)
    print('  restful.py: cleaned')


def cleanup_sse():
    """sse.py: remove X-Internal-Tenant-Id requirement."""
    content = read_file('sse.py')
    # Remove the tenant_id header parameter
    content = re.sub(
        r'\s*x_internal_tenant_id:\s*str\s*\|\s*None\s*=\s*Header\(default=None,\s*alias="X-Internal-Tenant-Id"\),?\s*\n',
        '\n',
        content,
    )
    # Remove the tenant_id validation block
    content = re.sub(
        r'\s*if not x_internal_tenant_id:\s*\n\s*raise HTTPException\(status_code=400,\s*detail="missing X-Internal-Tenant-Id"\)\s*\n\s*try:\s*\n\s*tenant_id\s*=\s*int\(x_internal_tenant_id\)\s*\n\s*except\s*\(ValueError,\s*TypeError\):\s*\n\s*raise HTTPException\(status_code=400,\s*detail="invalid X-Internal-Tenant-Id"\)\s*\n',
        '\n',
        content,
    )
    # Replace subscriber_id and tenant_id reference
    content = content.replace(
        'subscriber_id = f"tenant_{tenant_id}_{uuid.uuid4().hex[:8]}"',
        'subscriber_id = f"sse_{uuid.uuid4().hex[:8]}"'
    )
    content = content.replace(
        "yield f\"data: {json.dumps({'type': 'connected', 'message': '连接成功', 'tenantId': tenant_id})}\\n\\n\"",
        "yield f\"data: {json.dumps({'type': 'connected', 'message': '连接成功'})}\\n\\n\""
    )
    write_file('sse.py', content)
    print('  sse.py: cleaned')


def cleanup_system():
    """system.py: remove tenantId from response."""
    content = read_file('system.py')
    content = re.sub(r',?\s*"tenantId":\s*current_user\.get\("tenant_id"\)', '', content)
    write_file('system.py', content)
    print('  system.py: cleaned')


def cleanup_feishu():
    """feishu.py: simplify tenant resolution - use default tenant 1."""
    content = read_file('feishu.py')
    # Replace _resolve_tenant_id_from_tenant_key with a simple default
    content = re.sub(
        r'def _resolve_tenant_id_from_tenant_key\(tenant_key: str,\s*body: dict\)\s*->\s*int\s*\|\s*None:.*?(?=\n\n\n|\n# =)',
        'def _resolve_tenant_id_from_tenant_key(tenant_key: str, body: dict) -> int | None:\n    """单租户模式：直接返回默认租户 ID 1。"""\n    return 1\n',
        content,
        flags=re.DOTALL,
    )
    # Replace _find_single_feishu_app_tenant functions with default
    content = re.sub(
        r'async def _find_single_feishu_app_tenant_async\(\).*?(?=\n\n\n|\n# =|\ndef |\Z)',
        'async def _find_single_feishu_app_tenant_async() -> int | None:\n    """单租户模式：直接返回默认租户 ID 1。"""\n    return 1\n',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'def _find_single_feishu_app_tenant\(\).*?(?=\n\n\n|\n# =|\ndef |\nasync def |\Z)',
        'def _find_single_feishu_app_tenant() -> int | None:\n    """单租户模式：直接返回默认租户 ID 1。"""\n    return 1\n',
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r'def _find_single_feishu_app_tenant_sync\(\).*?(?=\n\n\n|\n# =|\ndef |\nasync def |\Z)',
        'def _find_single_feishu_app_tenant_sync() -> int | None:\n    """单租户模式：直接返回默认租户 ID 1。"""\n    return 1\n',
        content,
        flags=re.DOTALL,
    )
    # Remove "SELECT tenant_id, config_json FROM user_notification_setting" queries
    # and replace with simple config load
    content = re.sub(
        r'from sqlalchemy import text\s*\nfrom app\.core\.database import async_session\s*\n\s*async with async_session\(\) as db:\s*\n\s*rows = \(await db\.execute\(\s*text\(\s*"SELECT tenant_id, config_json FROM user_notification_setting "\s*"WHERE deleted = 0"\s*\)\s*\)\)\.mappings\(\)\.all\(\)\s*\n\s*decrypted = None\s*\n\s*tenant_id_found = None\s*\n\s*for row in rows:.*?body = decrypted\s*\n\s*tenant_id = tenant_id_found',
        'from app.services.feishu_bot import _load_feishu_app_config\n            tenant_id = 1\n            config = await _load_feishu_app_config(tenant_id)\n            if not config:\n                return JSONResponse(status_code=200, content={"code": 0, "msg": "not configured"})\n            body = body',
        content,
        flags=re.DOTALL,
    )
    # Remove tenant_id from feishu_config_check
    content = re.sub(
        r'\s*tenant_id\s*=\s*current_user\.get\("tenant_id"\)\s*\n\s*config\s*=\s*await _load_feishu_app_config\(tenant_id\)',
        '\n    config = await _load_feishu_app_config(1)',
        content,
    )
    # Replace remaining tenant_id references in feishu with 1
    # But keep the variable for logging - just set it to 1
    write_file('feishu.py', content)
    print('  feishu.py: cleaned (simplified tenant resolution to default 1)')


def main():
    print('=== Phase 4: Comprehensive tenant_id cleanup ===')
    cleanup_account()
    cleanup_auto_category()
    cleanup_auto_reply_scope()
    cleanup_captcha()
    cleanup_dashboard()
    cleanup_items()
    cleanup_kami()
    cleanup_messages()
    cleanup_misc()
    cleanup_quick_reply()
    cleanup_restful()
    cleanup_sse()
    cleanup_system()
    cleanup_feishu()
    print('\n=== Phase 4 complete ===')


if __name__ == '__main__':
    main()
