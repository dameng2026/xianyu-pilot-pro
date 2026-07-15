"""
最终综合验证脚本 v2
===================
修正 v1 的误报：
- feishu.py 的 tenant_id=1 是合法的 Feishu API 用法（与 feishu_bot.py 同理）
- automation_runtime 在 misc.py 中仅出现在注释/文档字符串，非实际 import

验证项：
1. 路由文件 tenant_id 检查（排除 feishu.py 合法用法、消息字段）
2. 服务文件 tenant_id 检查（feishu_bot.py 允许合法用法）
3. 路由文件禁止导入检查（用 AST 精确匹配 import/from...import）
4. misc.py 无搜索函数
5. items.py 无擦亮函数
6. xianyu_goods_sync.py 无搜索函数
7. 路由文件 user_id=user_id 残留检查
8. user_id 引用必须有对应的提取行（current_user.get("user_id")）
"""
import ast
import re
from pathlib import Path

TARGET = Path(r"G:\源码\项目借鉴\xianyu-assistant-opensource\apps\api\app")
ROUTES = TARGET / "api" / "v1" / "routes"
SERVICES = TARGET / "services"

FORBIDDEN_IMPORTS = {
    "automation_runtime",
    "opportunity",
    "workflow",
    "ai_transaction",
    "opportunity_draft_service",
}

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

# feishu.py 使用 tenant_id=1 作为 Feishu API 的本地变量（合法）
FEISHU_ROUTE_ALLOWLIST = {"feishu.py"}
# feishu_bot.py 使用 tenant_id 作为 Feishu tenant_access_token 缓存 key（合法）
FEISHU_SERVICE_ALLOWLIST = {"feishu_bot.py"}


def separator(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


def extract_imported_modules(source: str) -> set[str]:
    """用 AST 解析源码，提取所有 import 的模块名（顶层）"""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                mods.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
                # 也加上完整模块路径的各段
                parts = node.module.split(".")
                for p in parts:
                    mods.add(p)
    return mods


def check_routes_tenant_id() -> int:
    """检查路由文件中的 tenant_id（feishu.py 允许合法用法）"""
    separator("1. 路由文件 tenant_id 检查（feishu.py 允许合法 Feishu API 用法）")
    issues = 0
    for p in sorted(ROUTES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        count = c.count("tenant_id")
        if p.name in FEISHU_ROUTE_ALLOWLIST:
            print(f"  [OK]   {p.name}: {count} refs (合法 Feishu API tenant_access_token 用法)")
        elif count == 0:
            print(f"  [OK]   {p.name}: 0 refs")
        else:
            issues += count
            print(f"  [FAIL] {p.name}: {count} refs")
            for i, line in enumerate(c.splitlines(), 1):
                if "tenant_id" in line:
                    print(f"    L{i}: {line.rstrip()}")
    if issues == 0:
        print("  >> 路由文件 tenant_id 全部合规")
    return issues


def check_services_tenant_id() -> int:
    """检查服务文件中的 tenant_id（feishu_bot.py 允许合法用法）"""
    separator("2. 服务文件 tenant_id 检查（feishu_bot.py 允许合法用法）")
    issues = 0
    for p in sorted(SERVICES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        count = c.count("tenant_id")
        if p.name in FEISHU_SERVICE_ALLOWLIST:
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
    """检查路由文件中是否有禁止导入（AST 精确匹配）"""
    separator("3. 禁止导入检查（AST 精确匹配，排除注释/文档字符串）")
    issues = 0
    for p in sorted(ROUTES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        imported = extract_imported_modules(c)
        found = imported & FORBIDDEN_IMPORTS
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
    found = [kw for kw in SEARCH_MARKERS if kw in c]
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
    found = [kw for kw in POLISH_MARKERS if kw in c]
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
    found = [kw for kw in SEARCH_MARKERS if kw in c]
    if found:
        print(f"  [FAIL] xianyu_goods_sync.py: 发现搜索标记 {found}")
        return len(found)
    print("  [OK]   xianyu_goods_sync.py: 无搜索函数")
    return 0


def check_user_id_assignment() -> int:
    """检查 user_id=user_id 调用是否有对应的 user_id 提取行"""
    separator("7. user_id 提取行完整性检查")
    issues = 0
    for p in sorted(ROUTES.glob("*.py")):
        if p.name == "__init__.py":
            continue
        c = p.read_text(encoding="utf-8")
        # 检查 user_id=user_id 调用（作为函数参数传递）
        call_pattern = re.compile(r"user_id\s*=\s*user_id\b")
        # 检查 user_id 提取行
        extract_pattern = re.compile(r'user_id\s*=\s*current_user\.get\(\s*["\']user_id["\']\s*\)')

        calls = call_pattern.findall(c)
        extracts = extract_pattern.findall(c)

        if len(calls) > 0 and len(extracts) == 0:
            issues += len(calls)
            print(f"  [FAIL] {p.name}: {len(calls)} 处 user_id=user_id 但无提取行")
        elif len(calls) > 0:
            print(f"  [OK]   {p.name}: {len(calls)} 处调用, {len(extracts)} 处提取行")
        else:
            print(f"  [OK]   {p.name}: 无 user_id=user_id 调用")
    if issues == 0:
        print("  >> user_id 提取行完整性检查通过")
    return issues


def check_syntax() -> int:
    """检查所有 .py 文件语法是否正确"""
    separator("8. 语法检查（py_compile）")
    import py_compile
    issues = 0
    for d in [ROUTES, SERVICES]:
        for p in sorted(d.glob("*.py")):
            if p.name == "__init__.py":
                continue
            try:
                py_compile.compile(str(p), doraise=True, quiet=2)
                print(f"  [OK]   {p.name}")
            except py_compile.PyCompileError as e:
                issues += 1
                print(f"  [FAIL] {p.name}: {e}")
    if issues == 0:
        print("  >> 所有文件语法检查通过")
    return issues


def main() -> None:
    print("#" * 70)
    print("  最终综合验证 v2：迁移后目标项目合规性检查")
    print("#" * 70)

    total_issues = 0
    total_issues += check_routes_tenant_id()
    total_issues += check_services_tenant_id()
    total_issues += check_forbidden_imports()
    total_issues += check_misc_no_search()
    total_issues += check_items_no_polish()
    total_issues += check_goods_sync_no_search()
    total_issues += check_user_id_assignment()
    total_issues += check_syntax()

    separator("验证结果汇总")
    if total_issues == 0:
        print("  ✅ 全部验证通过！迁移完成。")
    else:
        print(f"  ❌ 共发现 {total_issues} 个问题需要修复。")
    print("=" * 70)


if __name__ == "__main__":
    main()
