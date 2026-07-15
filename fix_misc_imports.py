"""Fix misc.py imports - add back xianyu_qr_login and xianyu_goods_sync imports."""
import os

path = r'G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app\api\v1\routes\misc.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = (
    "from ....services.ws_client import ws_manager\n"
    "from ....services.ws_storage import save_chat_message\n"
    "from ....services.ws_sse import broadcaster\n"
    "\n"
    "# automation_runtime 模块未移植（工作流执行器）；update_ws_heartbeat 降级为 no-op\n"
    "async def update_ws_heartbeat(*args, **kwargs):\n"
    '    """No-op stub: 原本由 automation_runtime 提供，单租户精简版未移植该模块。"""\n'
    "    return None\n"
    "from ....services.auto_category import upload_image_to_xianyu as _upload_image_to_xianyu\n"
    "from ..deps import get_current_user"
)

new = (
    "from ....services.ws_client import ws_manager\n"
    "from ....services.ws_storage import save_chat_message\n"
    "from ....services.ws_sse import broadcaster\n"
    "from ....core.xianyu_qr_login import (\n"
    "    get_session_cookies, generate_qrcode, get_session_status, cleanup_all,\n"
    ")\n"
    "from ....services.xianyu_goods_sync import (\n"
    "    _get_token_from_cookie as _xianyu_token_from_cookie,\n"
    ")\n"
    "from ....services.auto_category import upload_image_to_xianyu as _upload_image_to_xianyu\n"
    "\n"
    "# automation_runtime 模块未移植（工作流执行器）；update_ws_heartbeat 降级为 no-op\n"
    "async def update_ws_heartbeat(*args, **kwargs):\n"
    '    """No-op stub: 原本由 automation_runtime 提供，单租户精简版未移植该模块。"""\n'
    "    return None\n"
    "from ..deps import get_current_user"
)

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK: fixed misc.py imports')
else:
    print('WARN: old import block not found')
    # Show the actual imports section for debugging
    for i, line in enumerate(content.split('\n')[:35], 1):
        print(f'{i}: {line}')
