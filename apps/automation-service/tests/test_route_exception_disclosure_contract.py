"""Static guard against returning exception internals from HTTP routes."""

from __future__ import annotations

import ast
from pathlib import Path


ROUTES_DIR = Path(__file__).parents[1] / "app" / "api" / "v1" / "routes"

def _call_name(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _references_exception(node: ast.AST, exception_name: str) -> bool:
    """Return True for exception detail used outside approved safe metadata."""

    for child in ast.walk(node):
        if isinstance(child, ast.Call) and _call_name(child) == "safe_route_failure":
            # The centralized helper consumes only the exception type.
            continue
        if isinstance(child, ast.Call) and _call_name(child) == "type":
            # ``type(exc).__name__`` is intentionally safe diagnostic metadata.
            continue
        if isinstance(child, ast.Name) and child.id == exception_name:
            return True
    return False


def _unsafe_returns(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    findings: list[str] = []

    functions = (
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    for function in functions:
        for handler in (node for node in ast.walk(function) if isinstance(node, ast.ExceptHandler)):
            if not handler.name:
                continue
            for statement in handler.body:
                for node in ast.walk(statement):
                    if not isinstance(node, ast.Return) or node.value is None:
                        continue
                    if _call_name(node.value) == "safe_route_failure":
                        continue
                    if (
                        isinstance(node.value, ast.Call)
                        and _call_name(node.value) == "failed"
                        and node.value.args
                        and isinstance(node.value.args[0], ast.Attribute)
                        and node.value.args[0].attr == "public_message"
                        and isinstance(node.value.args[0].value, ast.Name)
                        and node.value.args[0].value.id == handler.name
                    ):
                        # PublicRouteValidationError exposes a deliberately authored
                        # client message without converting the exception itself.
                        continue
                    if _references_exception(node.value, handler.name):
                        findings.append(f"{path.name}:{node.lineno}")

    return findings


def test_routes_do_not_return_exception_details():
    findings: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        findings.extend(_unsafe_returns(path))

    assert findings == [], (
        "Route exception details must be converted with safe_route_failure; "
        f"unsafe returns: {', '.join(findings)}"
    )
