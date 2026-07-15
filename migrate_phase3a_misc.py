"""
Phase 3a: Remove search-related code from misc.py.
- Remove business_router definition
- Remove _call_crawler_search, _call_mtop_search_direct, _detect_mtop_error,
  _execute_search_with_mode, business_goofish_search, internal_goofish_search functions
- Remove search-related imports from xianyu_goods_sync (keep _xianyu_token_from_cookie)
"""
import os
import re

MISC_PATH = r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes\misc.py"

with open(MISC_PATH, 'r', encoding='utf-8') as f:
    content = f.read()

# ============================================================
# 1. Clean up the xianyu_goods_sync import block - keep only _xianyu_token_from_cookie
# ============================================================
# Original block:
# from ....services.xianyu_goods_sync import (
#     _make_api_request as _xianyu_mtop_request,
#     _get_token_from_cookie as _xianyu_token_from_cookie,
#     _normalize_mtop_search_item,
#     _resolve_account_cookie,
#     SEARCH_MTOP_API,
#     TOKEN_EXPIRED as _XIANYU_TOKEN_EXPIRED,
#     TOKEN_EXPIRED_ALIAS as _XIANYU_TOKEN_EXPIRED_ALIAS,
#     RGV587 as _XIANYU_RGV587,
# )
old_import = '''from ....services.xianyu_goods_sync import (
    _make_api_request as _xianyu_mtop_request,
    _get_token_from_cookie as _xianyu_token_from_cookie,
    _normalize_mtop_search_item,
    _resolve_account_cookie,
    SEARCH_MTOP_API,
    TOKEN_EXPIRED as _XIANYU_TOKEN_EXPIRED,
    TOKEN_EXPIRED_ALIAS as _XIANYU_TOKEN_EXPIRED_ALIAS,
    RGV587 as _XIANYU_RGV587,
)'''
new_import = '''from ....services.xianyu_goods_sync import (
    _get_token_from_cookie as _xianyu_token_from_cookie,
)'''
if old_import in content:
    content = content.replace(old_import, new_import)
    print("OK: replaced xianyu_goods_sync import block")
else:
    print("WARN: could not find xianyu_goods_sync import block")

# ============================================================
# 2. Remove the business_router definition line
# ============================================================
content = re.sub(
    r'business_router\s*=\s*APIRouter\(prefix="/business-opportunity"\)\s*\n',
    '',
    content,
)

# ============================================================
# 3. Remove the entire search section (from comment header to end of file)
# ============================================================
# The search section starts with:
# # ---- Goofish MTOP 商品关键词搜索 ----
# and contains all the search functions through internal_goofish_search
search_section_pattern = r'\n# ---- Goofish MTOP 商品关键词搜索 ----.*$'
new_content = re.sub(search_section_pattern, '\n', content, flags=re.DOTALL)

if new_content != content:
    content = new_content
    print("OK: removed search section")
else:
    print("WARN: could not find search section")

# Also remove the orphan comment about _resolve_account_cookie if it remains
content = re.sub(
    r'\n# _resolve_account_cookie 和 _normalize_mtop_search_item 已移至[^\n]*\n',
    '\n',
    content,
)
content = re.sub(
    r'\n# SEARCH_MTOP_API, _resolve_account_cookie, _normalize_mtop_search_item 已移至[^\n]*\n',
    '\n',
    content,
)

# Clean up any remaining references to removed names in comments
content = re.sub(
    r'# 此端点是 Java 网关 /api/goofish/search 调用的目标。\n# 使用已登录闲鱼账号的 Cookie \+ _m_h5_tk 调用 MTOP 搜索 API。\n# SEARCH_MTOP_API, _resolve_account_cookie, _normalize_mtop_search_item 已移至\n# xianyu_goods_sync\.py 并在顶部导入，避免跨层导入失败。\n',
    '',
    content,
)

with open(MISC_PATH, 'w', encoding='utf-8') as f:
    f.write(content)

# Verify
remaining_search = sum(1 for name in ['_call_crawler_search', '_call_mtop_search_direct',
    '_detect_mtop_error', '_execute_search_with_mode', 'business_goofish_search',
    'internal_goofish_search', 'business_router', 'SEARCH_MTOP_API',
    '_normalize_mtop_search_item', '_resolve_account_cookie']
    if name in content)
print(f"Remaining search-related references: {remaining_search}")
print("=== misc.py search removal complete ===")
