import ast
from collections import defaultdict
from pathlib import Path


MOJIBAKE_MARKERS = (
    "\ufffd",
    "锟斤拷",
    "鏃犳硶",
    "璇锋眰",
    "澶辫触",
    "鐢ㄦ埛",
    "鍒嗛〉",
    "杩斿洖",
    "璋冪敤",
    "鍚庡彴",
    "鍔犺浇",
    "Cookie涓",
    "绛惧悕",
)


def test_python_modules_do_not_silently_override_top_level_functions():
    app_root = Path(__file__).resolve().parents[1] / "app"
    duplicates = []

    for source_path in app_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        definitions = defaultdict(list)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                definitions[node.name].append(node.lineno)
        for name, lines in definitions.items():
            if len(lines) > 1:
                duplicates.append(f"{source_path.relative_to(app_root)}:{name}:{lines}")

    assert duplicates == [], "duplicate top-level functions silently override behavior: " + "; ".join(duplicates)


def test_python_classes_do_not_silently_override_methods():
    app_root = Path(__file__).resolve().parents[1] / "app"
    duplicates = []

    for source_path in app_root.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            definitions = defaultdict(list)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    definitions[child.name].append(child.lineno)
            for name, lines in definitions.items():
                if len(lines) > 1:
                    duplicates.append(
                        f"{source_path.relative_to(app_root)}:{node.name}.{name}:{lines}"
                    )

    assert duplicates == [], "duplicate class methods silently override behavior: " + "; ".join(duplicates)


def test_application_source_does_not_contain_known_mojibake():
    app_root = Path(__file__).resolve().parents[1] / "app"
    findings = []

    for source_path in app_root.rglob("*.py"):
        source = source_path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            for marker in MOJIBAKE_MARKERS:
                if marker in line:
                    findings.append(
                        f"{source_path.relative_to(app_root)}:{line_number}:{marker}"
                    )

    assert findings == [], "application source contains mojibake: " + "; ".join(findings)
