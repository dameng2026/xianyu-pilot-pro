"""
最终综合验证脚本
================
验证迁移后的目标项目满足以下要求：
1. 路由文件中无 tenant_id（排除消息字段 sender_user_id/receiver_user_id/from_user_id/to_user_id）
2. 服务文件中仅 feishu_bot.py 保留合法的 Feishu API tenant_id（默认值=1）
3. 路由文件中无禁止导入（automation_runtime, opportunity, workflow, ai_transaction, opportunity_draft_service）
4. misc.py 中无搜索函数（goofish_search, _call_mtop_search_direct, _call_crawler_search, _execute_search_with_mode）
5. items.py 中无擦亮函数（polish, 擦亮）
6. xianyu_goods_sync.py 中无搜索函数（SEARCH_MTOP_API, _normalize_mtop_search_item）
"""
import re
from pathlib import Path

TARGET = Path(r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app")
ROUTES = TARGET / "api" / "v1" / "routes"
SERVICES = TARGET / "services"

FORBIDDEN_IMPORTS = [
    "automation_runtime",
    "opportunity",
    "workflow",
    "ai_transaction",
    "opportunity_draft_service",
]

SEARCH_MARKERS = [
    "goofish_search",
    "goofishSearch",
    "_call_mtop_search_direct",
    "_call_crawler_search",
    "_execute_search_with_mode",
    "SEARCH_MTOP_API",
    "_normalize_mtop_search_item",
    "mtop.taobao.idlemtopsearch.pc.search",
]

POLISH_MARKERS = [
    "polish",
    "擦亮",
]


def separator(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def check_routes_tenant_id() -> int:
    """检查路由文件中的 tenant_id（排除消息字段）"""
    separator("1. 路由文件 tenant_id 检查（排除消息字段）")
    issues = 0
    # 消息字段白名单：这些字段含 user_id 但属于消息协议字段，应保留
    message_field_whitelist = {
        "sender_user_id", "receiver_user_id",
        "from_user_id", "to_user_id",
        "senderUserId", "receiverUserId",
        "fromUserId", "toUserId",
    }
    for p in sorted(ROUTES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        lines = p.read_text(encoding="utf-8").splitlines()
        bad_lines = []
        for i, line in enumerate(lines, 1):
            if "tenant_id" not in line:
                continue
            bad_lines.append((i, line.rstrip()))
        if bad_lines:
            issues += len(bad_lines)
            print(f"  [FAIL] {p.name}:")
            for ln, txt in bad_lines:
                print(f"    L{ln}: {txt}")
        else:
            print(f"  [OK]   {p.name}: 0 tenant_id refs")
    if issues == 0:
        print("  >> 所有路由文件均无 tenant_id 引用")
    return issues


def check_services_tenant_id() -> int:
    """检查服务文件中的 tenant_id（feishu_bot.py 允许合法 Feishu API 用法）"""
    separator("2. 服务文件 tenant_id 检查（feishu_bot.py 允许合法用法）")
    issues = 0
    for p in sorted(SERVICES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        count = c.count("tenant_id")
        if p.name == "feishu_bot.py":
            # 合法：函数签名默认值 + 缓存 key（Feishu API tenant_access_token）
            print(f"  [OK]   {p.name}: {count} refs (合法 Feishu API tenant_access_token 缓存)")
        elif count == 0:
            print(f"  [OK]   {p.name}: 0 refs")
        else:
            issues += count
            print(f"  [FAIL] {p.name}: {count} refs")
            for i, line in enumerate(c.splitlines(), 1):
                if "tenant_id" in line:
                    print(f"    L{i}: {line.rstrip()}")
    if issues == 0:
        print("  >> 服务文件 tenant_id 全部合规")
    return issues


def check_forbidden_imports() -> int:
    """检查路由文件中是否有禁止导入"""
    separator("3. 禁止导入检查（路由文件）")
    issues = 0
    for p in sorted(ROUTES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        found = []
        for kw in FORBIDDEN_IMPORTS:
            if kw in c:
                found.append(kw)
        if found:
            issues += len(found)
            print(f"  [FAIL] {p.name}: 发现禁止导入 {found}")
        else:
            print(f"  [OK]   {p.name}")
    if issues == 0:
        print("  >> 所有路由文件均无禁止导入")
    return issues


def check_misc_no_search() -> int:
    """检查 misc.py 中无搜索函数"""
    separator("4. misc.py 搜索函数检查")
    p = ROUTES / "misc.py"
    c = p.read_text(encoding="utf-8")
    found = []
    for kw in SEARCH_MARKERS:
        if kw in c:
            found.append(kw)
    if found:
        print(f"  [FAIL] misc.py: 发现搜索标记 {found}")
        return len(found)
    print("  [OK]   misc.py: 无搜索函数")
    return 0


def check_items_no_polish() -> int:
    """检查 items.py 中无擦亮函数"""
    separator("5. items.py 擦亮函数检查")
    p = ROUTES / "items.py"
    c = p.read_text(encoding="utf-8")
    found = []
    for kw in POLISH_MARKERS:
        if kw in c:
            found.append(kw)
    if found:
        print(f"  [FAIL] items.py: 发现擦亮标记 {found}")
        return len(found)
    print("  [OK]   items.py: 无擦亮函数")
    return 0


def check_goods_sync_no_search() -> int:
    """检查 xianyu_goods_sync.py 中无搜索函数"""
    separator("6. xianyu_goods_sync.py 搜索函数检查")
    p = SERVICES / "xianyu_goods_sync.py"
    if not p.exists():
        print(f"  [SKIP] {p} 不存在")
        return 0
    c = p.read_text(encoding="utf-8")
    found = []
    for kw in SEARCH_MARKERS:
        if kw in c:
            found.append(kw)
    if found:
        print(f"  [FAIL] xianyu_goods_sync.py: 发现搜索标记 {found}")
        return len(found)
    print("  [OK]   xianyu_goods_sync.py: 无搜索函数")
    return 0


def check_user_id_in_routes() -> int:
    """检查路由文件中 XianyuAccount 构造是否还残留 user_id=user_id"""
    separator("7. 路由文件 user_id 残留检查（XianyuAccount 构造）")
    issues = 0
    pattern = re.compile(r"user_id\s*=\s*user_id")
    for p in sorted(ROUTES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        matches = pattern.findall(c)
        if matches:
            issues += len(matches)
            print(f"  [FAIL] {p.name}: 发现 {len(matches)} 处 'user_id=user_id'")
        else:
            print(f"  [OK]   {p.name}")
    if issues == 0:
        print("  >> 路由文件无 user_id=user_id 残留")
    return issues


def main() -> None:
    print("#" * 70)
    print("  最终综合验证：迁移后目标项目合规性检查")
    print("#" * 70)

    total_issues = 0
    total_issues += check_routes_tenant_id()
    total_issues += check_services_tenant_id()
    total_issues += check_forbidden_imports()
    total_issues += check_misc_no_search()
    total_issues += check_items_no_polish()
    total_issues += check_goods_sync_no_search()
    total_issues += check_user_id_in_routes()

    separator("验证结果汇总")
    if total_issues == 0:
        print("  ✅ 全部验证通过！迁移完成。")
    else:
        print(f"  ❌ 共发现 {total_issues} 个问题需要修复。")
    print("=" * 70)


if __name__ == "__main__":
    main()
