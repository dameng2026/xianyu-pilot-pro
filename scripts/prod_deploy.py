#!/usr/bin/env python3
import argparse
import fnmatch
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path, PurePosixPath

try:
    import paramiko
except ImportError:
    paramiko = None

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
from validate_migrations import MigrationValidationError, validate_repository
from incremental_sync import sync_items_to_staged


REPO_ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = REPO_ROOT / ".deploy-prod-artifacts"
DEFAULT_US_NGINX_CONFIG = REPO_ROOT / "deploy" / "nginx" / "us-nginx-full.conf"
DEFAULT_ORIGIN_TUNNEL_SERVICE_TEMPLATE = (
    REPO_ROOT / "deploy" / "systemd" / "xianyupilot-origin-tunnel.service.template"
)
ORIGIN_TUNNEL_HOST = "127.0.0.1"
ORIGIN_TUNNEL_PORT = 18081
ORIGIN_TUNNEL_HEALTH_PATH = "/api/health"
MANAGED_INFRASTRUCTURE_IMAGES = {
    "mysql": ("xianyu-admin-mysql", "mysql:8.4.10"),
    "redis": ("xianyu-crawler-redis", "redis:7.4.9-alpine"),
    "crawler-postgres": ("xianyu-crawler-postgres", "postgres:16.14-alpine"),
}
BACKEND_BUNDLE_ITEMS = [
    "apps/core-api",
    "apps/automation-service",
    "apps/crawler-service",
    "db/migrations-manifest.json",
    "scripts/validate_migrations.py",
    "scripts/incremental_sync.py",
    "scripts/production-preflight.sh",
    "scripts/prod_deploy.py",
    "deploy/nginx/us-nginx-full.conf",
    "deploy/systemd",
    "monitoring",
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker-compose.monitoring.yml",
    "docker-compose.infrastructure.yml",
    ".env.production.example",
    ".gitignore",
]
MONITORING_SERVICES = (
    "blackbox-exporter",
    "alertmanager",
    "prometheus",
    "grafana",
)
MONITORING_CONTAINERS = (
    "xianyu-blackbox-exporter",
    "xianyu-alertmanager",
    "xianyu-prometheus",
    "xianyu-grafana",
)
DEFAULT_RUNTIME_CONTAINER_NAMES = {
    "automation": "xianyu-automation-service",
    "automation-worker": "xianyu-automation-worker",
    "crawler-service": "xianyu-crawler-service",
    "crawler-worker": "xianyu-crawler-worker",
    "backend": "xianyu-admin-backend",
    "admin-web": "xianyu-admin-web",
    "user-web": "xianyu-user-web",
}
DOCKER_ENV_GUARD = (
    "unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES "
    "COMPOSE_ENV_FILES DOCKER_HOST DOCKER_CONTEXT; export DOCKER_CONTEXT=default; "
)
SAFE_REMOTE_PROJECT_ROOTS = (
    PurePosixPath("/data"),
    PurePosixPath("/home"),
    PurePosixPath("/opt"),
    PurePosixPath("/srv"),
    PurePosixPath("/var/www"),
)
EXCLUDED_DIR_NAMES = {
    ".cache",
    ".git",
    ".gradle",
    ".m2",
    ".mvn",
    ".mypy_cache",
    ".npm-bootstrap-cache",
    ".npm-cache",
    ".playwright-cli",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".tools",
    ".tox",
    ".trae",
    ".tmp",
    ".uploads",
    ".uv-cache",
    ".uv-tools",
    ".uv-tools-bin",
    ".venv",
    ".yarn-cache",
    "__pycache__",
    "coverage",
    "dist",
    "dogfood-output",
    "logs",
    "node_modules",
    "output",
    "screenshots",
    "target",
    "temp",
    "test",
    "tests",
    "tmp",
    "uploads",
    "verification-screenshots",
}
EXCLUDED_FILE_SUFFIXES = {
    ".7z",
    ".bak",
    ".class",
    ".codex-bak",
    ".err",
    ".jar",
    ".log",
    ".out",
    ".old",
    ".orig",
    ".pid",
    ".pyc",
    ".rej",
    ".swp",
    ".tar",
    ".tar.gz",
    ".temp",
    ".tgz",
    ".tmp",
    ".war",
    ".zip",
}
EXCLUDED_FILE_NAMES = {
    ".ds_store",
    ".release-revision",
    ".release-transaction",
    "thumbs.db",
}
SENSITIVE_FILE_PATTERNS = {
    "*.har": "HTTP session capture",
    "*_dump.json": "raw API capture",
    "*_response.json": "raw API response capture",
    "login-body.json": "login credential capture",
    "login_body.json": "login credential capture",
    "login-resp.json": "login response capture",
    "login_resp.json": "login response capture",
    "login-response.json": "login response capture",
    "login_response.json": "login response capture",
    "*login*capture*.json": "login session capture",
    "reset*pwd*.sql": "password reset artifact",
    "*.key": "private key file",
    "*.p12": "private key store",
    "*.pfx": "private key store",
    "*.pem": "PEM credential material",
    "*_token.txt": "token export",
    "*cookie*.json": "cookie export",
    "*cookie*.txt": "cookie export",
    "storage-state.json": "browser storage state",
    "storage_state.json": "browser storage state",
    "auth-state.json": "browser authentication state",
    "auth_state.json": "browser authentication state",
    ".netrc": "credential file",
    ".npmrc": "package registry credentials",
    ".pypirc": "package registry credentials",
    "id_rsa*": "SSH private key",
}
SECRET_ASSIGNMENT_SUFFIXES = {
    ".conf",
    ".ini",
    ".json",
    ".properties",
    ".toml",
    ".yaml",
    ".yml",
}
# Generated lockfiles key entries by package name (e.g. "js-tokens": "^9.0.0")
# and UI translation catalogs key entries by display label (e.g.
# "password": "请输入密码"); neither carries literal secret material, so the
# assignment scan skips them. Path-pattern and embedded-key checks still
# apply to these files.
LITERAL_SECRET_SCAN_EXEMPT_NAMES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "pnpm-lock.yaml",
    "yarn.lock",
}
LITERAL_SECRET_SCAN_EXEMPT_DIR_PARTS = {"i18n", "langs", "locales"}
SECRET_ASSIGNMENT_RE = re.compile(
    r"^\s*[\"']?([A-Za-z0-9_.-]*"
    r"(?:password|secret|token|api[-_]?key|private[-_]?key)"
    r"[A-Za-z0-9_.-]*)"
    r"[\"']?\s*[:=]\s*(.+?)\s*,?\s*$",
    re.IGNORECASE,
)
CONTAINER_SECRET_FILE_RE = re.compile(r"/run/secrets/[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
PLACEHOLDER_MARKERS = {
    "${",
    "{{",
    "123456",
    "change-me",
    "dev-only",
    "dummy",
    "mock",
    "placeholder",
    "replace-with",
    "sandbox",
}


class CommandError(RuntimeError):
    pass


class SecretPreflightError(CommandError):
    """Raised when a release input contains a secret-bearing path or value."""


class ProductionPreflightError(CommandError):
    """Raised before deployment when production transport guarantees are unsafe."""


class DeploymentRollback:
    """A compensating action retained until every release gate has passed."""

    def __init__(self, label, callback):
        self.label = label
        self._callback = callback

    def __call__(self):
        log(f"Rolling back: {self.label}")
        self._callback()


def log(message):
    print(f"[deploy] {message}", flush=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _operator_evidence_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ProductionPreflightError(
            "production migration evidence file must use an absolute path"
        )
    if path.is_symlink():
        raise ProductionPreflightError(
            "production migration evidence file must not be a symbolic link"
        )
    return path


def ensure_file(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")


def load_config(path: Path):
    ensure_file(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def is_excluded(rel_path: Path):
    lowered_parts = {part.lower() for part in rel_path.parts}
    if lowered_parts.intersection(EXCLUDED_DIR_NAMES):
        return True
    name = rel_path.name
    if _secret_path_reason(rel_path):
        return True
    lowered_name = name.lower()
    if lowered_name in EXCLUDED_FILE_NAMES:
        return True
    stem = Path(lowered_name).stem
    if (lowered_name.startswith(("test_", "debug_"))
            or stem.endswith(("_test", "_debug"))
            or ".test." in lowered_name
            or ".spec." in lowered_name):
        return True
    return any(lowered_name.endswith(suffix) for suffix in EXCLUDED_FILE_SUFFIXES)


def _is_env_example(name: str) -> bool:
    lowered = name.lower()
    return lowered == ".env.example" or lowered.endswith(".example")


def _secret_path_reason(rel_path: Path):
    name = rel_path.name.lower()
    if (name == ".env" or name.startswith(".env.")) and not _is_env_example(name):
        return "environment file"
    if name.startswith(".deploy") and name.endswith(".json") and ".example." not in name:
        return "real deployment configuration"
    for pattern, reason in SENSITIVE_FILE_PATTERNS.items():
        if fnmatch.fnmatch(name, pattern):
            return reason
    return None


def _literal_secret_assignment_reason(path: Path):
    if path.suffix.lower() not in SECRET_ASSIGNMENT_SUFFIXES:
        return None
    if path.name.lower() in LITERAL_SECRET_SCAN_EXEMPT_NAMES:
        return None
    if {part.lower() for part in path.parts} & LITERAL_SECRET_SCAN_EXEMPT_DIR_PARTS:
        return None
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            return None
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    for line in text.splitlines():
        match = SECRET_ASSIGNMENT_RE.match(line)
        if not match:
            continue
        key = match.group(1).lower()
        value = match.group(2).strip().strip("\"'")
        lowered = value.lower()
        # Docker/Grafana-style *_FILE variables contain a path, not the secret.
        # Accept only the fixed in-container secret mount namespace; arbitrary
        # host paths, traversal and interpolated values still fail closed.
        if key.endswith("_file") and CONTAINER_SECRET_FILE_RE.fullmatch(value):
            continue
        if (
            not value
            or lowered in {"null", "none", "true", "false"}
            or any(marker in lowered for marker in PLACEHOLDER_MARKERS)
        ):
            continue
        return "literal secret assignment"
    return None


def _embedded_secret_reason(path: Path):
    try:
        if path.stat().st_size > 5 * 1024 * 1024:
            return None
        payload = path.read_bytes()
    except OSError:
        return None
    # Split markers so the detection literal does not appear verbatim in this
    # source file (which would self-trigger the embedded-secret preflight).
    begin_marker = b"-----" + b"BEGIN "
    key_marker = b"PRIVATE" + b" KEY" + b"-----"
    if begin_marker in payload and key_marker in payload:
        return "embedded private key"
    return None


def _iter_preflight_paths(source: Path):
    if source.is_file() or source.is_symlink():
        yield source
        return

    for current_root, dir_names, file_names in os.walk(source, topdown=True, followlinks=False):
        current = Path(current_root)
        retained_dirs = []
        for dir_name in dir_names:
            path = current / dir_name
            rel = path.relative_to(source)
            if path.is_symlink():
                yield path
            elif not is_excluded(rel):
                retained_dirs.append(dir_name)
        dir_names[:] = retained_dirs

        for file_name in file_names:
            path = current / file_name
            rel = path.relative_to(source)
            if path.is_symlink() or not is_excluded(rel):
                yield path


def preflight_backend_bundle_inputs():
    missing = [item for item in BACKEND_BUNDLE_ITEMS if not (REPO_ROOT / item).exists()]
    if missing:
        raise FileNotFoundError(
            "Required backend bundle allowlist input(s) are missing: "
            + ", ".join(missing)
        )

    findings = []
    for item in BACKEND_BUNDLE_ITEMS:
        source = REPO_ROOT / item
        if not source.exists():
            continue
        for path in _iter_preflight_paths(source):
            rel = path.relative_to(REPO_ROOT)
            if path.is_symlink():
                findings.append((rel, "symbolic link"))
                continue
            if not path.is_file():
                continue
            reason = (
                _secret_path_reason(rel)
                or _literal_secret_assignment_reason(path)
                or _embedded_secret_reason(path)
            )
            if reason:
                findings.append((rel, reason))

    if findings:
        details = ", ".join(
            f"{str(path).replace(os.sep, '/')} ({reason})"
            for path, reason in findings
        )
        raise SecretPreflightError(
            "Release secret preflight rejected sensitive input path(s): " + details
        )


def preflight_release_tree(source: Path):
    findings = []
    for path in _iter_preflight_paths(source):
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path.relative_to(source)
        if path.is_symlink():
            findings.append((rel, "symbolic link"))
            continue
        if not path.is_file():
            continue
        reason = (
            _secret_path_reason(rel)
            or _literal_secret_assignment_reason(path)
            or _embedded_secret_reason(path)
        )
        if reason:
            findings.append((rel, reason))
    if findings:
        details = ", ".join(
            f"{str(path).replace(os.sep, '/')} ({reason})"
            for path, reason in findings
        )
        raise SecretPreflightError(
            "Release secret preflight rejected sensitive input path(s): " + details
        )


PRIVATE_UPSTREAM_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("::1/128"),
)


def _is_private_upstream_host(host: str) -> bool:
    lowered = host.lower().rstrip(".")
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return (
            "." not in lowered
            or lowered.endswith(".internal")
            or lowered.endswith(".local")
            or lowered.endswith(".localhost")
        )
    return any(address in network for network in PRIVATE_UPSTREAM_NETWORKS)


def _parse_nginx_blocks(text: str):
    root = {"parent": None, "directives": []}
    blocks = [root]
    stack = [root]
    buffer = []
    line_number = 1
    statement_line = 1
    quote = None
    escaped = False
    in_comment = False

    def flush_directive():
        statement = "".join(buffer).strip()
        buffer.clear()
        if not statement:
            return
        parts = statement.split(None, 1)
        name = parts[0].lower()
        arguments = parts[1].strip() if len(parts) > 1 else ""
        stack[-1]["directives"].append((name, arguments, statement_line))

    for char in text:
        if in_comment:
            if char == "\n":
                in_comment = False
                line_number += 1
            continue

        if quote is not None:
            buffer.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            if char == "\n":
                line_number += 1
            continue

        if char == "#":
            in_comment = True
            continue
        if char in {"'", '"'}:
            if not buffer or not "".join(buffer).strip():
                statement_line = line_number
            quote = char
            buffer.append(char)
            continue
        if char == "{":
            header = "".join(buffer).strip()
            buffer.clear()
            block = {
                "parent": stack[-1],
                "directives": [],
                "header": header,
                "line": statement_line,
            }
            blocks.append(block)
            stack.append(block)
            statement_line = line_number
            continue
        if char == ";":
            flush_directive()
            statement_line = line_number
            continue
        if char == "}":
            if "".join(buffer).strip():
                raise ProductionPreflightError(
                    f"Nginx config has an unterminated directive before line {line_number}"
                )
            buffer.clear()
            if len(stack) == 1:
                raise ProductionPreflightError("Nginx config has an unmatched closing brace")
            stack.pop()
            statement_line = line_number
            continue
        if not "".join(buffer).strip() and not char.isspace():
            statement_line = line_number
        buffer.append(char)
        if char == "\n":
            line_number += 1

    if quote is not None:
        raise ProductionPreflightError("Nginx config has an unterminated quoted string")
    if len(stack) != 1:
        raise ProductionPreflightError("Nginx config has an unclosed block")
    if "".join(buffer).strip():
        raise ProductionPreflightError("Nginx config has an unterminated directive")
    return blocks


def _effective_nginx_directive(block, name: str):
    current = block
    while current is not None:
        matches = [
            arguments
            for directive_name, arguments, _line in current["directives"]
            if directive_name == name
        ]
        if matches:
            return matches[-1]
        current = current["parent"]
    return None


def _nginx_upstream_server_hosts(blocks):
    """Map nginx upstream block names to the host addresses of member servers."""
    upstreams = {}
    for block in blocks:
        header = block.get("header") or ""
        parts = header.split()
        if len(parts) < 2 or parts[0].lower() != "upstream":
            continue
        name = parts[1].strip("\"'")
        hosts = []
        for directive_name, arguments, _line in block["directives"]:
            if directive_name != "server" or not arguments:
                continue
            target = arguments.split()[0].strip("\"'")
            if target.startswith("["):
                closing = target.find("]")
                hosts.append(target[1:closing] if closing > 0 else target)
                continue
            hosts.append(target.rsplit(":", 1)[0] if ":" in target else target)
        upstreams[name] = hosts
    return upstreams


def _host_routes_privately(host: str, upstream_servers: dict) -> bool:
    lowered = host.lower().rstrip(".")
    if not _is_private_upstream_host(lowered):
        return False
    # A dotless name usually references an nginx upstream block; trusting the
    # label alone would let a public origin hide behind it, so every member
    # server must also route privately.
    member_hosts = upstream_servers.get(lowered)
    if member_hosts is None:
        return True
    return all(_is_private_upstream_host(member) for member in member_hosts)


def validate_nginx_transport_security(path: Path):
    ensure_file(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ProductionPreflightError(f"Nginx config is not valid UTF-8: {path}") from exc

    blocks = _parse_nginx_blocks(text)
    upstream_servers = _nginx_upstream_server_hosts(blocks)
    unverifiable_findings = []
    plaintext_findings = []
    https_findings = []
    for block in blocks:
        for name, arguments, line_number in block["directives"]:
            if name != "proxy_pass":
                continue
            target = arguments.split()[0].strip("\"'") if arguments else ""
            if "$" in target or not re.match(r"^https?://", target, re.IGNORECASE):
                unverifiable_findings.append(f"line {line_number}")
                continue
            parsed = urllib.parse.urlsplit(target)
            host = parsed.hostname
            if parsed.scheme.lower() == "https":
                missing = []
                verify = _effective_nginx_directive(block, "proxy_ssl_verify")
                if (verify or "").lower() != "on":
                    missing.append("proxy_ssl_verify on")
                server_name = _effective_nginx_directive(
                    block, "proxy_ssl_server_name"
                )
                if (server_name or "").lower() != "on":
                    missing.append("proxy_ssl_server_name on")
                if not _effective_nginx_directive(block, "proxy_ssl_trusted_certificate"):
                    missing.append("proxy_ssl_trusted_certificate")
                if missing:
                    https_findings.append(
                        (line_number, host or "<invalid-host>", missing)
                    )
                continue
            if host and "$" not in host and _host_routes_privately(
                host, upstream_servers
            ):
                continue
            plaintext_findings.append(
                f"line {line_number} host {host or '<invalid-host>'}"
            )

    if unverifiable_findings:
        raise ProductionPreflightError(
            f"Nginx config {path} contains dynamic or unsupported proxy_pass target(s) "
            f"that the release preflight cannot verify: {', '.join(unverifiable_findings)}. "
            "Use a static verified HTTPS origin or a static VPN/private address."
        )

    if plaintext_findings:
        raise ProductionPreflightError(
            f"Nginx config {path} contains public plaintext HTTP upstream(s): "
            + ", ".join(plaintext_findings)
            + ". Use HTTPS with certificate verification (mTLS where available), "
            "or route HTTP only over a verified VPN/private address. "
            "Client-facing TLS does not encrypt the origin hop."
        )

    if https_findings:
        details = "; ".join(
            f"line {line_number} host {host} missing {', '.join(missing)}"
            for line_number, host, missing in https_findings
        )
        raise ProductionPreflightError(
            f"Nginx config {path} has HTTPS upstream(s) without explicit certificate "
            f"verification: {details}. Use a trusted CA bundle and mTLS where available."
        )


def nginx_uses_managed_origin_tunnel(path: Path) -> bool:
    """Return whether the candidate routes HTTP through the managed loopback tunnel."""
    ensure_file(path)
    try:
        blocks = _parse_nginx_blocks(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise ProductionPreflightError(f"Nginx config is not valid UTF-8: {path}") from exc

    for block in blocks:
        for name, arguments, _line_number in block["directives"]:
            if name != "proxy_pass" or not arguments:
                continue
            target = arguments.split()[0].strip("\"'")
            if "$" in target or not target.lower().startswith("http://"):
                continue
            parsed = urllib.parse.urlsplit(target)
            try:
                port = parsed.port or 80
            except ValueError:
                continue
            host = (parsed.hostname or "").lower().rstrip(".")
            is_loopback = host == "localhost"
            if not is_loopback:
                try:
                    is_loopback = ipaddress.ip_address(host).is_loopback
                except ValueError:
                    is_loopback = False
            if is_loopback and port == ORIGIN_TUNNEL_PORT:
                return True
    return False


def validate_origin_tunnel_service_template(
    path: Path = DEFAULT_ORIGIN_TUNNEL_SERVICE_TEMPLATE,
):
    """Fail closed if the tracked SSH tunnel service loses its security controls."""
    ensure_file(path)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ProductionPreflightError(
            f"Origin tunnel service template is not valid UTF-8: {path}"
        ) from exc

    required_fragments = (
        "User=xianyupilot-tunnel",
        "Group=xianyupilot-tunnel",
        "ExecStart=/usr/bin/ssh -N",
        "BatchMode=yes",
        "ExitOnForwardFailure=yes",
        "StrictHostKeyChecking=yes",
        "UserKnownHostsFile=/etc/xianyupilot-origin-tunnel/known_hosts",
        "IdentitiesOnly=yes",
        "PasswordAuthentication=no",
        "KbdInteractiveAuthentication=no",
        "GatewayPorts=no",
        f"-L {ORIGIN_TUNNEL_HOST}:{ORIGIN_TUNNEL_PORT}:127.0.0.1:18080",
        "NoNewPrivileges=yes",
        "PrivateTmp=yes",
        "PrivateDevices=yes",
        "ProtectSystem=strict",
        "ProtectHome=read-only",
        "RestrictSUIDSGID=yes",
        "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6",
        "CapabilityBoundingSet=",
    )
    missing = [fragment for fragment in required_fragments if fragment not in text]
    forbidden_fragments = (
        "User=root",
        "StrictHostKeyChecking=no",
        "GatewayPorts=yes",
        f"-L 0.0.0.0:{ORIGIN_TUNNEL_PORT}",
        f"-L [::]:{ORIGIN_TUNNEL_PORT}",
    )
    forbidden = [fragment for fragment in forbidden_fragments if fragment in text]
    if missing or forbidden:
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if forbidden:
            details.append("forbidden " + ", ".join(forbidden))
        raise ProductionPreflightError(
            f"Origin tunnel service template {path} is unsafe: " + "; ".join(details)
        )


def _validated_origin_tunnel_runtime(frontend: dict) -> tuple[str, str]:
    service = frontend.get(
        "origin_tunnel_service", "xianyupilot-origin-tunnel.service"
    )
    if not isinstance(service, str) or not re.fullmatch(r"[A-Za-z0-9@_.-]+", service):
        raise ProductionPreflightError("origin_tunnel_service is not a safe systemd unit name")

    health_url = frontend.get(
        "origin_tunnel_health_url",
        f"http://{ORIGIN_TUNNEL_HOST}:{ORIGIN_TUNNEL_PORT}{ORIGIN_TUNNEL_HEALTH_PATH}",
    )
    if not isinstance(health_url, str):
        raise ProductionPreflightError("origin_tunnel_health_url must be a string")
    parsed = urllib.parse.urlsplit(health_url)
    try:
        port = parsed.port or 80
    except ValueError as exc:
        raise ProductionPreflightError("origin_tunnel_health_url has an invalid port") from exc
    if (
        parsed.scheme != "http"
        or parsed.hostname != ORIGIN_TUNNEL_HOST
        or port != ORIGIN_TUNNEL_PORT
        or parsed.path != ORIGIN_TUNNEL_HEALTH_PATH
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ProductionPreflightError(
            "origin_tunnel_health_url must be the managed loopback /api/health endpoint"
        )
    return service, health_url


def _validated_public_https_base(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductionPreflightError(f"{label} is required")
    normalized = value.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(normalized)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ProductionPreflightError(
            f"{label} must be an explicit credential-free HTTPS origin"
        )
    return normalized


def _validated_external_health_urls(backend: dict) -> list[str]:
    legacy = backend.get("health_urls")
    configured = backend.get("external_health_urls", legacy or [])
    if configured is None:
        return []
    if not isinstance(configured, list):
        raise ProductionPreflightError("external_health_urls must be a list")

    result = []
    for value in configured:
        if not isinstance(value, str) or not value.strip():
            raise ProductionPreflightError("external_health_urls contains an invalid URL")
        url = value.strip()
        parsed = urllib.parse.urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ProductionPreflightError(
                "external_health_urls must contain credential-free HTTPS URLs only"
            )
        result.append(url)
    return result


def _validated_backend_health_urls(config: dict, backend: dict) -> list[str]:
    configured = _validated_external_health_urls(backend)
    if configured:
        return configured
    smoke = config.get("smoke")
    if smoke is None:
        return []
    if not isinstance(smoke, dict):
        raise ProductionPreflightError("smoke must be an object")
    user_base = _validated_public_https_base(
        smoke.get("user_frontend_base"),
        "smoke.user_frontend_base",
    )
    admin_base = _validated_public_https_base(
        smoke.get("admin_frontend_base"),
        "smoke.admin_frontend_base",
    )
    return [
        user_base + "/api/health",
        admin_base + "/admin-api/health",
    ]


def _validated_backend_container_name(backend: dict) -> str:
    name = backend.get("backend_container_name", "xianyu-admin-backend")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
        raise ProductionPreflightError("backend_container_name is invalid")
    return name


def _validated_remote_project_dir(backend: dict) -> str:
    raw = backend.get("project_dir")
    if (
        not isinstance(raw, str)
        or not raw.startswith("/")
        or any(ord(char) < 32 or ord(char) == 127 for char in raw)
    ):
        raise ProductionPreflightError("china_backend.project_dir must be an absolute POSIX path")
    candidate = raw.rstrip("/")
    path = PurePosixPath(candidate)
    normalized = str(path)
    if (
        normalized in {"", "/"}
        or ".." in path.parts
        or normalized != candidate
        or not any(path != root and path.is_relative_to(root) for root in SAFE_REMOTE_PROJECT_ROOTS)
    ):
        raise ProductionPreflightError(
            "china_backend.project_dir must be a canonical application path under "
            "/home, /opt, /srv, /data, or /var/www; system roots and traversal are forbidden"
        )
    return normalized


def _validated_remote_path_below(
    value: object,
    field: str,
    approved_roots: tuple[PurePosixPath, ...],
) -> str:
    if (
        not isinstance(value, str)
        or not value.startswith("/")
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ProductionPreflightError(f"{field} must be an absolute POSIX path")
    candidate = value.rstrip("/")
    path = PurePosixPath(candidate)
    if (
        not candidate
        or str(path) != candidate
        or ".." in path.parts
        or not any(path != root and path.is_relative_to(root) for root in approved_roots)
    ):
        roots = ", ".join(str(root) for root in approved_roots)
        raise ProductionPreflightError(
            f"{field} must be a canonical child path below: {roots}"
        )
    return candidate


def _validated_frontend_layout(frontend: dict) -> tuple[str, str, str, str, str]:
    web_roots = (PurePosixPath("/var/www"),)
    user_root = _validated_remote_path_below(
        frontend.get("user_web_root"),
        "us_frontend.user_web_root",
        web_roots,
    )
    admin_root = _validated_remote_path_below(
        frontend.get("admin_web_root"),
        "us_frontend.admin_web_root",
        web_roots,
    )
    backup_root = _validated_remote_path_below(
        frontend.get("backup_root", "/var/www/backups"),
        "us_frontend.backup_root",
        web_roots,
    )
    release_root = _validated_remote_path_below(
        frontend.get("release_root", "/var/www/.releases"),
        "us_frontend.release_root",
        web_roots,
    )
    nginx_site_path = _validated_remote_path_below(
        frontend.get(
            "nginx_site_path",
            "/etc/nginx/sites-enabled/nginx-full.conf",
        ),
        "us_frontend.nginx_site_path",
        (PurePosixPath("/etc/nginx"),),
    )

    directory_paths = {
        "user_web_root": PurePosixPath(user_root),
        "admin_web_root": PurePosixPath(admin_root),
        "backup_root": PurePosixPath(backup_root),
        "release_root": PurePosixPath(release_root),
    }
    items = list(directory_paths.items())
    for index, (left_name, left_path) in enumerate(items):
        for right_name, right_path in items[index + 1 :]:
            if left_path.is_relative_to(right_path) or right_path.is_relative_to(left_path):
                raise ProductionPreflightError(
                    "US frontend live/backup/release paths must not overlap: "
                    f"{left_name}, {right_name}"
                )

    return user_root, admin_root, backup_root, release_root, nginx_site_path


def _validated_remote_compose_env(project_dir: str, value: object) -> tuple[str, bool]:
    if (
        not isinstance(value, str)
        or not value.strip()
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ProductionPreflightError("compose_env_file is invalid")
    candidate = value.strip()
    path = PurePosixPath(candidate)
    if ".." in path.parts:
        raise ProductionPreflightError("compose_env_file must not contain traversal")
    if candidate.startswith("/"):
        normalized = str(path)
        if candidate == "/" or normalized != candidate:
            raise ProductionPreflightError("compose_env_file must name a file")
        project_path = PurePosixPath(project_dir)
        if path == project_path:
            raise ProductionPreflightError("compose_env_file must name a file, not project_dir")
        # An absolute path can still live inside the source tree. Such a file must
        # be held outside the directory rename and restored into the new release.
        return normalized, not path.is_relative_to(project_path)
    if candidate.startswith("./"):
        candidate = candidate[2:]
    if not candidate or candidate.startswith("/"):
        raise ProductionPreflightError("compose_env_file is invalid")
    return f"{project_dir}/{candidate}", False


def _validated_release_revision(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ProductionPreflightError(
            "production deployment requires the exact lowercase Git release revision"
        )
    return value


def _validated_runtime_container_names(
    backend: dict,
    runtime_services: list[str],
    backend_container_name: str,
) -> list[str]:
    configured = backend.get("runtime_container_names", {})
    if configured is None:
        configured = {}
    if not isinstance(configured, dict):
        raise ProductionPreflightError("runtime_container_names must be an object")

    defaults = dict(DEFAULT_RUNTIME_CONTAINER_NAMES)
    defaults["backend"] = backend_container_name
    result: list[str] = []
    for service in runtime_services:
        if not isinstance(service, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", service):
            raise ProductionPreflightError("runtime services contain an invalid service name")
        name = configured.get(service, defaults.get(service))
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", name):
            raise ProductionPreflightError(
                f"runtime service {service} requires a valid runtime_container_names entry"
            )
        if name not in result:
            result.append(name)
    if not result:
        raise ProductionPreflightError("at least one runtime container must be health-gated")
    return result


def _infrastructure_image_guard_script(infra_services: list[str]) -> str | None:
    checks = []
    for service in infra_services:
        managed = MANAGED_INFRASTRUCTURE_IMAGES.get(service)
        if managed is None:
            continue
        container_name, expected_image = managed
        current_var = f"current_{service.replace('-', '_')}"
        checks.append(
            f"{current_var}=$(docker inspect --format={shlex.quote('{{.Config.Image}}')} "
            f"{shlex.quote(container_name)} 2>/dev/null || true); "
            f"if [ -n \"${current_var}\" ] "
            f"&& [ \"${current_var}\" != {shlex.quote(expected_image)} ] "
            f"&& [ \"${current_var}\" != {shlex.quote('docker.io/library/' + expected_image)} ]; then "
            f"echo {shlex.quote('[deploy] managed infrastructure image drift for ' + service + '; complete the reviewed backup/migration runbook first')} >&2; "
            "exit 42; fi"
        )
    if not checks:
        return None
    return "set -euo pipefail; " + DOCKER_ENV_GUARD + "; ".join(checks)


def _container_health_wait_script(container_names: list[str] | tuple[str, ...], label: str) -> str:
    """Build a composable fail-closed Docker health wait for remote Bash."""
    names = " ".join(shlex.quote(name) for name in container_names)
    health_template = "{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}"
    return (
        DOCKER_ENV_GUARD
        + f"containers=({names}); healthy=0; "
        "for attempt in $(seq 1 60); do "
        "all_healthy=1; "
        "for container in \"${containers[@]}\"; do "
        f"status=$(docker inspect --format={shlex.quote(health_template)} \"$container\" 2>/dev/null || true); "
        "if [ -z \"$status\" ] || [ \"$status\" = missing ]; then "
        f"echo \"[deploy] {label} container $container is missing or has no healthcheck\" >&2; exit 1; fi; "
        "if [ \"$status\" = unhealthy ]; then "
        f"echo \"[deploy] {label} container $container is unhealthy\" >&2; exit 1; fi; "
        "if [ \"$status\" != healthy ]; then all_healthy=0; fi; "
        "done; "
        "if [ \"$all_healthy\" = 1 ]; then healthy=1; break; fi; "
        "sleep 5; "
        "done; "
        f"if [ \"$healthy\" != 1 ]; then echo '[deploy] {label} containers did not become healthy' >&2; exit 1; fi"
    )


def resolve_repo_path(value: str | os.PathLike[str]) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def validate_git_tracked_sensitive_paths():
    git = shutil.which("git")
    if not git:
        return
    completed = subprocess.run(
        [git, "-C", str(REPO_ROOT), "ls-files", "-z"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return

    findings = []
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        rel = Path(os.fsdecode(raw_path))
        path = REPO_ROOT / rel
        reason = (
            _secret_path_reason(rel)
            or _literal_secret_assignment_reason(path)
            or _embedded_secret_reason(path)
        )
        if reason:
            findings.append((rel, reason))
    if findings:
        details = ", ".join(
            f"{str(path).replace(os.sep, '/')} ({reason})"
            for path, reason in findings
        )
        raise SecretPreflightError(
            "Sensitive path(s) or content are tracked by Git and must be removed from "
            "the index without deleting required local files: " + details
        )


def validate_clean_release_revision(root: Path = REPO_ROOT) -> str:
    """Require an immutable, clean Git source before any production mutation."""
    git = shutil.which("git")
    if not git:
        raise ProductionPreflightError("Git is required for a production release")

    revision_result = subprocess.run(
        [git, "-C", str(root), "rev-parse", "--verify", "HEAD"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    revision = revision_result.stdout.strip().lower()
    if revision_result.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise ProductionPreflightError(
            "Production deployment requires a real Git repository with a committed revision"
        )

    status_result = subprocess.run(
        [git, "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if status_result.returncode != 0:
        raise ProductionPreflightError("Cannot verify the production release worktree")
    if status_result.stdout:
        # Do not print paths: a dirty path itself may disclose a secret artifact.
        raise ProductionPreflightError(
            "Production deployment requires a clean worktree; commit the reviewed release first"
        )
    return revision


def _assert_release_worktree_unchanged(expected_revision: str) -> None:
    actual_revision = validate_clean_release_revision()
    if actual_revision != expected_revision:
        raise ProductionPreflightError(
            "release source revision changed after the deployment transaction started"
        )


def validate_migration_manifest(
    *,
    production: bool = False,
    evidence_file: Path | None = None,
    release_id: str | None = None,
    release_revision: str | None = None,
):
    try:
        return validate_repository(
            root=REPO_ROOT,
            manifest_path=REPO_ROOT / "db" / "migrations-manifest.json",
            production=production,
            evidence_path=evidence_file,
            release_id=release_id,
            release_revision=release_revision,
        )
    except MigrationValidationError as exc:
        raise ProductionPreflightError(str(exc)) from None


def run_release_preflight(*, include_backend: bool, nginx_config: Path | None):
    validate_git_tracked_sensitive_paths()
    if include_backend:
        validate_migration_manifest()
        preflight_backend_bundle_inputs()
    if nginx_config is not None:
        validate_nginx_transport_security(nginx_config)
        if nginx_uses_managed_origin_tunnel(nginx_config):
            validate_origin_tunnel_service_template()


def add_tree_to_tar(tar: tarfile.TarFile, source: Path):
    if not source.exists():
        return
    if source.is_file():
        rel = source.relative_to(REPO_ROOT)
        if not is_excluded(rel):
            tar.add(source, arcname=str(rel).replace("\\", "/"))
        return

    for current_root, dir_names, file_names in os.walk(
        source,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_root)
        retained_dirs = []
        for dir_name in dir_names:
            path = current / dir_name
            rel = path.relative_to(REPO_ROOT)
            if is_excluded(rel):
                continue
            if path.is_symlink():
                raise SecretPreflightError(
                    "Release bundle input changed after preflight (symbolic link): "
                    + str(rel).replace(os.sep, "/")
                )
            retained_dirs.append(dir_name)
            tar.add(path, arcname=str(rel).replace("\\", "/"), recursive=False)
        dir_names[:] = retained_dirs

        for file_name in file_names:
            path = current / file_name
            rel = path.relative_to(REPO_ROOT)
            if is_excluded(rel):
                continue
            if path.is_symlink():
                raise SecretPreflightError(
                    "Release bundle input changed after preflight (symbolic link): "
                    + str(rel).replace(os.sep, "/")
                )
            tar.add(path, arcname=str(rel).replace("\\", "/"), recursive=False)


def create_backend_bundle():
    preflight_backend_bundle_inputs()
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle_path = ARTIFACT_DIR / f"backend-src-{timestamp}.tar.gz"
    log(f"Creating backend bundle: {bundle_path}")
    with tarfile.open(bundle_path, "w:gz") as tar:
        for item in BACKEND_BUNDLE_ITEMS:
            add_tree_to_tar(tar, REPO_ROOT / item)
    return bundle_path


def create_dist_bundle(app_name: str, dist_dir: Path, dry_run: bool = False):
    if dry_run and not dist_dir.is_dir():
        return ARTIFACT_DIR / f"{app_name}-dist-dry-run.tar.gz"
    if not dist_dir.is_dir():
        raise FileNotFoundError(f"Build output not found: {dist_dir}")
    preflight_release_tree(dist_dir)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bundle_path = ARTIFACT_DIR / f"{app_name}-dist-{timestamp}.tar.gz"
    log(f"Packing {app_name} dist: {bundle_path}")
    with tarfile.open(bundle_path, "w:gz") as tar:
        for path in dist_dir.rglob("*"):
            rel = path.relative_to(dist_dir)
            if is_excluded(rel):
                continue
            tar.add(path, arcname=str(rel).replace("\\", "/"), recursive=False)
    return bundle_path


def sync_backend_to_staged(remote, staged_project_dir, project_dir, dry_run=False):
    """增量同步后端源码到远端 staged 目录（替代全量 tar.gz 上传）。

    通过 md5 比对本地与远端 live 目录，只上传变更文件，未变更文件在远端
    本地 cp 复制（磁盘操作），最后逐文件 md5 校验确保 staged 与本地完全一致。
    """
    items = [(REPO_ROOT / item, item) for item in BACKEND_BUNDLE_ITEMS]
    return sync_items_to_staged(
        remote.client,
        items,
        staged_project_dir,
        project_dir,
        exclude_fn=is_excluded,
        dry_run=dry_run,
        log=log,
    )


def sync_frontend_to_staged(
    remote,
    user_stage,
    admin_stage,
    user_live,
    admin_live,
    user_dist_dir,
    admin_dist_dir,
    dry_run=False,
):
    """增量同步前端 dist 到远端 staged 目录（替代全量 tar.gz 上传）。

    user-web 和 admin-web 分别同步到各自的 staged 目录，以各自的 live 目录
    作为 md5 比对基准。
    """
    sync_items_to_staged(
        remote.client,
        [(user_dist_dir, "")],
        user_stage,
        user_live,
        exclude_fn=is_excluded,
        dry_run=dry_run,
        log=log,
    )
    sync_items_to_staged(
        remote.client,
        [(admin_dist_dir, "")],
        admin_stage,
        admin_live,
        exclude_fn=is_excluded,
        dry_run=dry_run,
        log=log,
    )


def resolve_local_command(command):
    if not command:
        return command

    executable = command[0]
    if Path(executable).suffix:
        resolved = shutil.which(executable)
        return [resolved or executable, *command[1:]]

    candidates = [executable]
    if os.name == "nt":
        candidates.extend([f"{executable}.cmd", f"{executable}.exe", f"{executable}.bat"])

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, *command[1:]]

    return command


def run_local(command, cwd: Path, dry_run: bool):
    resolved_command = resolve_local_command(command)
    rendered = " ".join(shlex.quote(part) for part in command)
    log(f"Local: (cd {cwd}) {rendered}")
    if dry_run:
        return
    completed = subprocess.run(resolved_command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise CommandError(f"Local command failed with exit code {completed.returncode}: {rendered}")


class RemoteHost:
    def __init__(self, name, config, dry_run: bool):
        self.name = name
        self.config = config
        self.dry_run = dry_run
        self.client = None

    def __enter__(self):
        if self.dry_run:
            log(f"[dry-run] Skip SSH connect: {self.name}")
            return self
        if paramiko is None:
            raise ProductionPreflightError(
                "paramiko is required for remote SSH deployment but is not installed"
            )
        key_filename = self.config.get("key_filename")
        if key_filename and self.config.get("password"):
            raise ProductionPreflightError(
                f"SSH config for {self.name} must not combine key and password authentication"
            )
        known_hosts_path = None
        known_hosts_file = self.config.get("known_hosts_file")
        if known_hosts_file:
            known_hosts_path = Path(known_hosts_file).expanduser()
            ensure_file(known_hosts_path)
        key_path = None
        if key_filename:
            key_path = Path(key_filename).expanduser()
            ensure_file(key_path)

        client = paramiko.SSHClient()
        try:
            client.load_system_host_keys()
            if known_hosts_path is not None:
                client.load_host_keys(str(known_hosts_path))
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
            connect_kwargs = {
                "hostname": self.config["host"],
                "port": int(self.config.get("port", 22)),
                "username": self.config["username"],
                "timeout": 20,
                "look_for_keys": not bool(self.config.get("password")),
                "allow_agent": not bool(self.config.get("password")),
            }
            if key_path is not None:
                connect_kwargs["key_filename"] = str(key_path)
                connect_kwargs["look_for_keys"] = False
                connect_kwargs["allow_agent"] = False
            if self.config.get("password"):
                connect_kwargs["password"] = self.config["password"]
            client.connect(**connect_kwargs)
        except Exception:
            client.close()
            raise
        self.client = client
        log(f"Connected: {self.name}")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.client is not None:
            self.client.close()
            log(f"Disconnected: {self.name}")

    def upload(self, local_path: Path, remote_path: str):
        log(f"Upload: {local_path} -> {self.name}:{remote_path}")
        if self.dry_run:
            return
        assert self.client is not None
        sftp = self.client.open_sftp()
        try:
            sftp.put(str(local_path), remote_path)
        finally:
            sftp.close()

    def run(self, command: str, check: bool = True, timeout: int = 1800):
        log(f"Remote[{self.name}]: {command}")
        if self.dry_run:
            return "", "", 0
        assert self.client is not None
        stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
        if stdin is not None and hasattr(stdin, "close"):
            stdin.close()

        channel = stdout.channel
        started = time.time()
        out_chunks: list[str] = []
        err_chunks: list[str] = []

        while True:
            made_progress = False

            while channel.recv_ready():
                chunk = channel.recv(65536)
                if not chunk:
                    break
                text = chunk.decode("utf-8", "ignore")
                out_chunks.append(text)
                print(text, end="")
                made_progress = True

            while channel.recv_stderr_ready():
                chunk = channel.recv_stderr(65536)
                if not chunk:
                    break
                text = chunk.decode("utf-8", "ignore")
                err_chunks.append(text)
                print(text, end="", file=sys.stderr)
                made_progress = True

            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break

            if timeout and time.time() - started > timeout:
                channel.close()
                raise CommandError(f"Remote command timed out on {self.name}: {command}")

            if not made_progress:
                time.sleep(0.1)

        exit_code = channel.recv_exit_status()
        out = "".join(out_chunks)
        err = "".join(err_chunks)
        if check and exit_code != 0:
            raise CommandError(f"Remote command failed on {self.name} with exit code {exit_code}: {command}")
        return out, err, exit_code


def wait_for_http_ok(url: str, timeout_seconds: int, expect_json_key: str | None = None):
    started = time.time()
    last_error = None
    while time.time() - started < timeout_seconds:
        try:
            # 必须显式设置 User-Agent：WAF 对 urllib 默认 UA 返回 403
            request = urllib.request.Request(
                url,
                method="GET",
                headers={"User-Agent": "xianyupilot-deploy-smoke/1.0"},
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = response.read().decode("utf-8", "ignore")
                if expect_json_key and expect_json_key not in payload:
                    raise RuntimeError(f"Response missing marker {expect_json_key!r}: {payload[:200]}")
                return payload
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def request_text(
    url: str,
    method: str = "GET",
    data=None,
    timeout: int = 20,
    headers: dict[str, str] | None = None,
):
    body = None
    request_headers = dict(headers or {})
    request_headers.setdefault("User-Agent", "xianyupilot-deploy-smoke/1.0")
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8", "ignore")
        return response.status, text


def request_json(
    url: str,
    method: str = "GET",
    data=None,
    timeout: int = 20,
    headers: dict[str, str] | None = None,
):
    status, text = request_text(
        url,
        method=method,
        data=data,
        timeout=timeout,
        headers=headers,
    )
    return status, text, json.loads(text)


def _require_success_result(name: str, status: int, parsed: object) -> object:
    if status != 200:
        raise RuntimeError(f"{name} failed with HTTP {status}")
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{name} returned an invalid JSON result envelope")
    if parsed.get("code") not in {0, 200}:
        code = parsed.get("code")
        safe_code = code if isinstance(code, (int, float)) else "unexpected"
        raise RuntimeError(f"{name} failed with application code {safe_code}")
    return parsed.get("data")


def _require_smoke_token(name: str, data: object) -> str:
    if not isinstance(data, dict):
        raise RuntimeError(f"{name} did not return authentication data")
    token = data.get("token")
    if (
        not isinstance(token, str)
        or not token.strip()
        or len(token) > 8192
        or any(ord(character) < 32 or ord(character) == 127 for character in token)
    ):
        raise RuntimeError(f"{name} did not return a valid access token")
    return token.strip()


def run_smoke_checks(config, target: str, dry_run: bool):
    smoke = config["smoke"]
    user_base = _validated_public_https_base(
        smoke.get("user_frontend_base"), "smoke.user_frontend_base"
    )
    admin_base = _validated_public_https_base(
        smoke.get("admin_frontend_base"), "smoke.admin_frontend_base"
    )
    if dry_run:
        log("[dry-run] Skip smoke checks")
        return

    health_checks = []
    if target in {"all", "backend"}:
        health_checks.extend([
            ("Public user API health", user_base + "/api/health", None),
            ("Public admin API health", admin_base + "/admin-api/health", None),
        ])

    page_checks = []
    if target in {"all", "frontend"}:
        page_checks.extend([
            ("US user homepage", user_base + "/", None),
            ("US admin homepage", admin_base + "/", None),
        ])

    login_checks = [
        (
            "Public user login",
            user_base + "/api/login/login",
            smoke["user_credentials"],
            "POST",
            user_base + "/api/system/currentUser",
        ),
        (
            "Public admin login",
            admin_base + "/admin-api/auth/login",
            smoke["admin_credentials"],
            "GET",
            admin_base + "/admin-api/user/info",
        ),
    ]

    for name, url, _payload in health_checks:
        log(f"Smoke: {name} -> {url}")
        status, _text, parsed = request_json(url, method="GET", data=None)
        data = _require_success_result(name, status, parsed)
        if not isinstance(data, dict) or data.get("status") != "UP":
            raise RuntimeError(f"{name} did not report status UP")

    for name, url, _payload in page_checks:
        log(f"Smoke: {name} -> {url}")
        status, _text = request_text(url, method="GET", data=None)
        if status != 200:
            raise RuntimeError(f"{name} failed with HTTP {status}")

    for name, url, payload, session_method, session_url in login_checks:
        log(f"Smoke: {name} -> {url}")
        status, _text, parsed = request_json(url, method="POST", data=payload)
        token = _require_smoke_token(
            name,
            _require_success_result(name, status, parsed),
        )

        session_name = name.replace(" login", " authenticated session")
        log(f"Smoke: {session_name} -> {session_url}")
        status, _text, parsed = request_json(
            session_url,
            method=session_method,
            data=None,
            headers={"Authorization": f"Bearer {token}"},
        )
        session_data = _require_success_result(session_name, status, parsed)
        if not isinstance(session_data, dict) or not session_data:
            raise RuntimeError(f"{session_name} returned no authenticated identity")


def deploy_backend(
    config,
    dry_run: bool,
    deploy_mode: str = "all",
    release_revision: str | None = None,
    release_id: str | None = None,
    migration_evidence_sha256: str | None = None,
    verify_local_source: bool = False,
):
    backend = config["china_backend"]
    external_health_urls = _validated_backend_health_urls(config, backend)
    backend_container_name = _validated_backend_container_name(backend)
    compose_env = backend.get("compose_env_file", ".env.production")
    project_dir = _validated_remote_project_dir(backend)
    compose_env_path, compose_env_is_absolute = _validated_remote_compose_env(
        project_dir,
        compose_env,
    )
    release_key = _validated_release_revision(release_revision)
    has_release_evidence_binding = (
        release_id is not None or migration_evidence_sha256 is not None
    )
    if has_release_evidence_binding:
        if (
            not isinstance(release_id, str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,127}", release_id)
        ):
            raise ProductionPreflightError(
                "backend deployment requires the validated migration evidence release ID"
            )
        if (
            not isinstance(migration_evidence_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", migration_evidence_sha256)
        ):
            raise ProductionPreflightError(
                "backend deployment requires the validated migration evidence SHA-256"
            )
    if verify_local_source:
        _assert_release_worktree_unchanged(release_key)
    preflight_backend_bundle_inputs()
    release_stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    release_transaction = f"{release_key}:{release_stamp}"
    staged_project_dir = f"{project_dir}.release-{release_key[:16]}"
    previous_project_dir = f"{project_dir}.previous-{release_stamp}"
    failed_project_dir = f"{project_dir}.failed-{release_stamp}"
    env_hold_path = f"{project_dir}.env-hold-{release_stamp}"
    services = backend.get(
        "services",
        [
            "mysql",
            "redis",
            "crawler-postgres",
            "automation",
            "automation-worker",
            "crawler-service",
            "crawler-worker",
            "backend",
        ],
    )
    infra_services = backend.get("infra_services", ["mysql", "redis", "crawler-postgres"])
    infra_service_set = set(infra_services)
    runtime_services = backend.get(
        "runtime_services",
        [service for service in services if service not in infra_service_set],
    )
    backend_target_services = backend.get("backend_target_services", ["backend"])
    infra_services = [service for service in services if service in infra_service_set]
    infra_services_to_start = infra_services if deploy_mode != "backend" else []
    if deploy_mode == "backend":
        recreate_services = [
            service for service in backend_target_services if service in services
        ] or ["backend"]
    else:
        recreate_services = runtime_services or services
    runtime_containers_to_wait = _validated_runtime_container_names(
        backend,
        recreate_services,
        backend_container_name,
    )
    runtime_health_wait = _container_health_wait_script(
        runtime_containers_to_wait,
        "runtime",
    )
    monitoring_health_wait = _container_health_wait_script(
        MONITORING_CONTAINERS,
        "monitoring",
    )

    with RemoteHost("china-backend", backend, dry_run) as remote:
        validation_cmd = (
            "bash -lc "
            + shlex.quote(
                f"set -euo pipefail; "
                f"project_parent=$(dirname -- {shlex.quote(project_dir)}); "
                "resolved_project_parent=$(readlink -f -- \"$project_parent\"); "
                "case \"$resolved_project_parent\" in "
                "/home|/home/*|/opt|/opt/*|/srv|/srv/*|/data|/data/*|/var/www|/var/www/*) ;; "
                "*) echo '[deploy] resolved project parent escapes approved application roots' >&2; exit 1 ;; esac; "
                f"if [ -L {shlex.quote(project_dir)} ] "
                f"|| {{ [ -e {shlex.quote(project_dir)} ] && [ ! -d {shlex.quote(project_dir)} ]; }}; then "
                "echo '[deploy] live project path must be a real directory, not a symlink or file' >&2; exit 1; fi; "
                f"if [ -e {shlex.quote(staged_project_dir)} ] || [ -L {shlex.quote(staged_project_dir)} ] "
                f"|| [ -e {shlex.quote(previous_project_dir)} ] || [ -L {shlex.quote(previous_project_dir)} ] "
                f"|| [ -e {shlex.quote(failed_project_dir)} ] || [ -L {shlex.quote(failed_project_dir)} ] "
                f"|| [ -e {shlex.quote(env_hold_path)} ] || [ -L {shlex.quote(env_hold_path)} ]; then "
                "echo '[deploy] release staging path collision' >&2; exit 1; fi; "
                f"mkdir -p {shlex.quote(staged_project_dir)}"
            )
        )
        remote.run(validation_cmd)
        sync_backend_to_staged(remote, staged_project_dir, project_dir, dry_run=dry_run)
        if verify_local_source:
            _assert_release_worktree_unchanged(release_key)

        remote_preflight_binding = ""
        if has_release_evidence_binding:
            remote_preflight_binding = (
                f" {shlex.quote(release_id)}"
                f" {shlex.quote(migration_evidence_sha256)}"
            )
        remote_preflight = (
            "bash -lc "
            + shlex.quote(
                f"set -euo pipefail; cd {shlex.quote(staged_project_dir)}; "
                f"bash scripts/production-preflight.sh {shlex.quote(compose_env_path)} "
                f"deploy/nginx/us-nginx-full.conf {shlex.quote(release_key)}"
                f"{remote_preflight_binding}"
            )
        )
        remote.run(remote_preflight, timeout=300)

        # Read MONITORING_ENABLED from the remote env file to decide whether
        # to deploy and health-check the monitoring stack.
        monitoring_check_cmd = (
            "bash -lc "
            + shlex.quote(
                f"set -euo pipefail; "
                f"grep -E '^MONITORING_ENABLED=' {shlex.quote(compose_env_path)} "
                f"| head -1 | cut -d= -f2-"
            )
        )
        _mon_out, _mon_err, _mon_rc = remote.run(
            monitoring_check_cmd, check=False, timeout=30
        )
        monitoring_enabled = (_mon_out or "").strip() == "true"
        if monitoring_enabled:
            log("[deploy] Monitoring enabled; will deploy monitoring containers")
        else:
            log("[deploy] Monitoring disabled; skipping monitoring containers")

        # A narrow backend patch deliberately leaves monitoring untouched, but
        # it must never cut over while the mandatory production observers are
        # absent or unhealthy.  Check before activation to avoid changing live
        # source for a pre-existing monitoring outage, then check again after
        # the runtime replacement below.
        if deploy_mode == "backend" and monitoring_enabled:
            pre_cutover_monitoring_health = (
                "set -euo pipefail; " + monitoring_health_wait
            )
            remote.run(
                "bash -lc " + shlex.quote(pre_cutover_monitoring_health),
                timeout=330,
            )

        infrastructure_guard = _infrastructure_image_guard_script(infra_services_to_start)
        if infrastructure_guard:
            remote.run("bash -lc " + shlex.quote(infrastructure_guard), timeout=30)

        env_activation = ""
        if not compose_env_is_absolute:
            env_activation = (
                f"test -f {shlex.quote(compose_env_path)}; "
                f"test ! -L {shlex.quote(compose_env_path)}; "
                f"mv {shlex.quote(compose_env_path)} {shlex.quote(env_hold_path)}; env_held=1; "
            )
        env_restore = ""
        env_capture_from_new = ""
        if not compose_env_is_absolute:
            env_restore = (
                f"mkdir -p \"$(dirname -- {shlex.quote(compose_env_path)})\"; "
                f"if [ -e {shlex.quote(env_hold_path)} ]; then "
                f"mv {shlex.quote(env_hold_path)} {shlex.quote(compose_env_path)}; fi; "
            )
            env_capture_from_new = (
                f"if [ -f {shlex.quote(compose_env_path)} ]; then "
                f"mv {shlex.quote(compose_env_path)} {shlex.quote(env_hold_path)}; fi; "
            )
        activation_script = (
            "set -Eeuo pipefail; previous_moved=0; staged_moved=0; env_held=0; "
            + "rollback_activation() { rc=${1:-$?}; trap - ERR HUP INT TERM; set +e; "
            + env_capture_from_new
            + f"if [ \"$staged_moved\" -eq 1 ] && [ -e {shlex.quote(project_dir)} ]; then "
            + f"mv {shlex.quote(project_dir)} {shlex.quote(failed_project_dir)}; fi; "
            + f"if [ \"$previous_moved\" -eq 1 ] && [ -e {shlex.quote(previous_project_dir)} ]; then "
            + f"mv {shlex.quote(previous_project_dir)} {shlex.quote(project_dir)}; fi; "
            + env_restore
            + "exit \"$rc\"; }; trap rollback_activation ERR; "
            + "trap 'rollback_activation 129' HUP; "
            + "trap 'rollback_activation 130' INT; "
            + "trap 'rollback_activation 143' TERM; "
            + env_activation
            + f"if [ -e {shlex.quote(project_dir)} ]; then "
            + f"mv {shlex.quote(project_dir)} {shlex.quote(previous_project_dir)}; previous_moved=1; fi; "
            + f"mv {shlex.quote(staged_project_dir)} {shlex.quote(project_dir)}; staged_moved=1; "
            + f"printf '%s\n' {shlex.quote(release_key)} > {shlex.quote(project_dir + '/.release-revision')}; "
            + f"printf '%s\n' {shlex.quote(release_transaction)} > {shlex.quote(project_dir + '/.release-transaction')}; "
            + env_restore
            + "trap - ERR HUP INT TERM"
        )
        remote.run("bash -lc " + shlex.quote(activation_script), timeout=120)

        command_parts = [
            f"cd {shlex.quote(project_dir)}",
        ]
        if infra_services_to_start:
            infra_services_text = " ".join(
                shlex.quote(service) for service in infra_services_to_start
            )
            command_parts.append(
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} up -d {infra_services_text}"
            )

        if deploy_mode == "backend":
            recreate_services_text = " ".join(shlex.quote(service) for service in recreate_services)
            command_parts.append(
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} build {recreate_services_text}"
            )
            command_parts.append(
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} up -d --no-deps --force-recreate {recreate_services_text}"
            )
        else:
            recreate_services_text = " ".join(shlex.quote(service) for service in recreate_services)
            command_parts.append(
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} up -d --build --force-recreate {recreate_services_text}"
            )
            if monitoring_enabled:
                monitoring_services_text = " ".join(shlex.quote(service) for service in MONITORING_SERVICES)
                command_parts.append(
                    "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                    "-f docker-compose.monitoring.yml --profile monitoring "
                    f"--env-file {shlex.quote(compose_env_path)} up -d --force-recreate {monitoring_services_text}"
                )
                command_parts.append(
                    "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                    "-f docker-compose.monitoring.yml --profile monitoring "
                    f"--env-file {shlex.quote(compose_env_path)} ps"
                )
        if deploy_mode == "backend":
            command_parts.append(
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} ps"
            )
        deploy_cmd = (
            "bash -lc "
            + shlex.quote(
                "set -euo pipefail; " + DOCKER_ENV_GUARD + "; ".join(command_parts)
            )
        )
        rollback_parts = [f"cd {shlex.quote(project_dir)}"]
        if infra_services_to_start:
            rollback_parts.append(
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} up -d {infra_services_text}"
            )
        if deploy_mode == "backend":
            rollback_parts.extend([
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} build {recreate_services_text}",
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} up -d --no-deps --force-recreate {recreate_services_text}",
                runtime_health_wait,
            ])
        else:
            rollback_parts.extend([
                "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                f"--env-file {shlex.quote(compose_env_path)} up -d --build --force-recreate {recreate_services_text}",
                runtime_health_wait,
            ])
            if monitoring_enabled:
                rollback_parts.append(
                    "docker compose -f docker-compose.yml -f docker-compose.prod.yml "
                    "-f docker-compose.monitoring.yml --profile monitoring "
                    f"--env-file {shlex.quote(compose_env_path)} up -d --force-recreate {monitoring_services_text}"
                )
                rollback_parts.append(monitoring_health_wait)
        rollback_script = (
            "set -Eeuo pipefail; "
            + DOCKER_ENV_GUARD
            + f"if [ ! -e {shlex.quote(previous_project_dir)} ]; then "
            + "echo '[deploy] no previous source release was available for rollback' >&2; exit 44; fi; "
            + f"if [ ! -f {shlex.quote(project_dir + '/.release-revision')} ] "
            + f"|| ! grep -Fqx -- {shlex.quote(release_key)} "
            + f"{shlex.quote(project_dir + '/.release-revision')}; then "
            + "echo '[deploy] live backend revision changed; refusing stale rollback' >&2; exit 45; fi; "
            + f"if [ ! -f {shlex.quote(project_dir + '/.release-transaction')} ] "
            + f"|| ! grep -Fqx -- {shlex.quote(release_transaction)} "
            + f"{shlex.quote(project_dir + '/.release-transaction')}; then "
            + "echo '[deploy] live backend transaction changed; refusing stale rollback' >&2; exit 45; fi; "
            + env_capture_from_new
            + f"if [ -e {shlex.quote(project_dir)} ]; then "
            + f"mv {shlex.quote(project_dir)} {shlex.quote(failed_project_dir)}; fi; "
            + f"mv {shlex.quote(previous_project_dir)} {shlex.quote(project_dir)}; "
            + env_restore
            + "; ".join(rollback_parts)
        )
        rollback_cmd = "bash -lc " + shlex.quote(rollback_script)

        def rollback_release(original_error: Exception) -> None:
            try:
                _stdout, _stderr, exit_code = remote.run(
                    rollback_cmd,
                    check=False,
                    timeout=7200,
                )
            except Exception as rollback_error:
                raise CommandError(
                    "Release failed and previous source/runtime rollback could not be executed"
                ) from rollback_error
            if exit_code != 0:
                raise CommandError(
                    "Release failed and previous source/runtime rollback did not complete"
                ) from original_error

        def run_release_command(command: str, *, timeout: int) -> None:
            try:
                remote.run(command, timeout=timeout)
            except Exception as exc:
                rollback_release(exc)
                raise

        run_release_command(deploy_cmd, timeout=7200)

        runtime_health_script = (
            "set -euo pipefail; "
            + runtime_health_wait
        )
        run_release_command(
            "bash -lc " + shlex.quote(runtime_health_script),
            timeout=330,
        )

        if monitoring_enabled:
            monitoring_health_script = (
                "set -euo pipefail; "
                + monitoring_health_wait
            )
            run_release_command(
                "bash -lc " + shlex.quote(monitoring_health_script),
                timeout=330,
            )

        try:
            for url in external_health_urls:
                marker = '"UP"' if "readiness" in url or "health" in url else None
                log(f"Waiting for external backend health: {url}")
                if not dry_run:
                    wait_for_http_ok(url, timeout_seconds=300, expect_json_key=marker)
        except Exception as exc:
            rollback_release(exc)
            raise

    def rollback_after_release_gate():
        try:
            with RemoteHost("china-backend-rollback", backend, dry_run) as rollback_remote:
                _stdout, _stderr, exit_code = rollback_remote.run(
                    rollback_cmd,
                    check=False,
                    timeout=7200,
                )
        except Exception as exc:
            raise CommandError(
                "Post-deployment backend rollback could not be executed"
            ) from exc
        if exit_code != 0:
            raise CommandError(
                "Post-deployment backend source/runtime rollback did not complete"
            )

    return DeploymentRollback("China backend source and runtime", rollback_after_release_gate)


def deploy_frontend(
    config,
    skip_frontend_build: bool,
    dry_run: bool,
    release_revision: str | None = None,
    verify_local_source: bool = False,
):
    if skip_frontend_build and not dry_run:
        raise ProductionPreflightError(
            "--skip-frontend-build is permitted only with --dry-run"
        )
    release_key = _validated_release_revision(release_revision)
    if verify_local_source:
        _assert_release_worktree_unchanged(release_key)
    frontend = config["us_frontend"]
    (
        user_root,
        admin_root,
        backup_root,
        release_root,
        nginx_site_path,
    ) = _validated_frontend_layout(frontend)

    nginx_config_path = resolve_repo_path(
        frontend.get("nginx_config_source", str(DEFAULT_US_NGINX_CONFIG))
    )
    validate_nginx_transport_security(nginx_config_path)
    requires_origin_tunnel = nginx_uses_managed_origin_tunnel(nginx_config_path)
    origin_tunnel_service = None
    origin_tunnel_health_url = None
    if requires_origin_tunnel:
        validate_origin_tunnel_service_template()
        origin_tunnel_service, origin_tunnel_health_url = _validated_origin_tunnel_runtime(
            frontend
        )

    if not skip_frontend_build:
        run_local(["npm", "run", "build"], REPO_ROOT / "apps" / "user-web", dry_run)
        run_local(["npm", "run", "typecheck"], REPO_ROOT / "apps" / "admin-web", dry_run)
        run_local(["npm", "run", "build"], REPO_ROOT / "apps" / "admin-web", dry_run)

    user_dist_dir = REPO_ROOT / "apps" / "user-web" / "dist"
    admin_dist_dir = REPO_ROOT / "apps" / "admin-web" / "dist"
    if not dry_run:
        if not user_dist_dir.is_dir():
            raise FileNotFoundError(f"Build output not found: {user_dist_dir}")
        if not admin_dist_dir.is_dir():
            raise FileNotFoundError(f"Build output not found: {admin_dist_dir}")
        preflight_release_tree(user_dist_dir)
        preflight_release_tree(admin_dist_dir)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    rollback_state = (
        f"{backup_root}/.frontend-rollback-{timestamp}-{release_key[:12]}"
    )
    release_transaction = f"{release_key}:{timestamp}"
    user_stage = f"{release_root}/user-web-{timestamp}"
    admin_stage = f"{release_root}/admin-web-{timestamp}"
    user_failed = f"{release_root}/user-web-failed-{timestamp}"
    admin_failed = f"{release_root}/admin-web-failed-{timestamp}"
    ensure_file(nginx_config_path)
    remote_nginx_bundle = f"/tmp/us-nginx-full-{timestamp}.conf"
    nginx_test_command = frontend.get("nginx_test_command", "nginx -t")
    nginx_reload_command = frontend.get("nginx_reload_command", "systemctl reload nginx")

    with RemoteHost("us-frontend", frontend, dry_run) as remote:
        if requires_origin_tunnel:
            tunnel_check = (
                "set -euo pipefail; "
                f"systemctl is-active --quiet {shlex.quote(origin_tunnel_service)}; "
                f"curl --fail --silent --show-error --max-time 10 {shlex.quote(origin_tunnel_health_url)} "
                "| grep -q '\"UP\"'"
            )
            remote.run("bash -lc " + shlex.quote(tunnel_check), timeout=30)
        remote.upload(nginx_config_path, remote_nginx_bundle)

        pre_validation_cmd = (
            "bash -lc "
            + shlex.quote(
                f"set -euo pipefail; "
                f"mkdir -p {shlex.quote(backup_root)} {shlex.quote(release_root)}; "
                f"for candidate in {shlex.quote(user_stage)} {shlex.quote(admin_stage)} "
                f"{shlex.quote(backup_root + '/user-web-' + timestamp)} "
                f"{shlex.quote(backup_root + '/admin-web-' + timestamp)} "
                f"{shlex.quote(rollback_state)} {shlex.quote(user_failed)} {shlex.quote(admin_failed)}; do "
                "if [ -e \"$candidate\" ] || [ -L \"$candidate\" ]; then "
                "echo '[deploy] frontend release path collision' >&2; exit 1; fi; done; "
                f"mkdir -p {shlex.quote(user_stage)} {shlex.quote(admin_stage)}; "
                f"mkdir -m 700 {shlex.quote(rollback_state)}"
            )
        )
        remote.run(pre_validation_cmd)

        sync_frontend_to_staged(
            remote,
            user_stage,
            admin_stage,
            user_root,
            admin_root,
            user_dist_dir,
            admin_dist_dir,
            dry_run=dry_run,
        )
        if verify_local_source:
            _assert_release_worktree_unchanged(release_key)

        cutover_script = f"""
set -Eeuo pipefail
USER_STAGE={shlex.quote(user_stage)}
ADMIN_STAGE={shlex.quote(admin_stage)}
USER_BACKUP={shlex.quote(backup_root + '/user-web-' + timestamp)}
ADMIN_BACKUP={shlex.quote(backup_root + '/admin-web-' + timestamp)}
ROLLBACK_STATE={shlex.quote(rollback_state)}
NGINX_SITE={shlex.quote(nginx_site_path)}
NGINX_STAGE={shlex.quote(remote_nginx_bundle)}
NGINX_BACKUP={shlex.quote(backup_root + '/nginx-full.conf.bak-' + timestamp)}
USER_BACKED_UP=0
USER_INSTALLED=0
ADMIN_BACKED_UP=0
ADMIN_INSTALLED=0
NGINX_HAD_LIVE=0
NGINX_CHANGE_STARTED=0

rollback() {{
  exit_code=$?
  trap - ERR
  set +e
  rollback_failed=0
  echo "[deploy] frontend cutover failed; restoring previous release" >&2
  rm -rf "$USER_STAGE" "$ADMIN_STAGE" || rollback_failed=1
  rm -f "$NGINX_STAGE" || rollback_failed=1
  if [ "$USER_INSTALLED" -eq 1 ]; then
    rm -rf {shlex.quote(user_root)} || rollback_failed=1
  fi
  if [ "$USER_BACKED_UP" -eq 1 ]; then
    if [ -d "$USER_BACKUP" ] && [ ! -L "$USER_BACKUP" ]; then
      mv "$USER_BACKUP" {shlex.quote(user_root)} || rollback_failed=1
    else
      rollback_failed=1
    fi
  fi
  if [ "$ADMIN_INSTALLED" -eq 1 ]; then
    rm -rf {shlex.quote(admin_root)} || rollback_failed=1
  fi
  if [ "$ADMIN_BACKED_UP" -eq 1 ]; then
    if [ -d "$ADMIN_BACKUP" ] && [ ! -L "$ADMIN_BACKUP" ]; then
      mv "$ADMIN_BACKUP" {shlex.quote(admin_root)} || rollback_failed=1
    else
      rollback_failed=1
    fi
  fi
  if [ "$NGINX_CHANGE_STARTED" -eq 1 ]; then
    if [ "$NGINX_HAD_LIVE" -eq 1 ]; then
      if [ -f "$NGINX_BACKUP" ] && [ ! -L "$NGINX_BACKUP" ]; then
        cp "$NGINX_BACKUP" "$NGINX_SITE" || rollback_failed=1
      else
        rollback_failed=1
      fi
    else
      rm -f "$NGINX_SITE" || rollback_failed=1
    fi
    if {nginx_test_command}; then
      {nginx_reload_command} || rollback_failed=1
    else
      rollback_failed=1
    fi
  fi
  if [ "$rollback_failed" -ne 0 ]; then
    echo "[deploy] frontend rollback did not complete" >&2
    exit 70
  fi
  rm -rf "$ROLLBACK_STATE" || {{
    echo "[deploy] frontend rollback state cleanup failed" >&2
    exit 70
  }}
  exit "$exit_code"
}}

trap rollback ERR
chmod -R 755 "$USER_STAGE" "$ADMIN_STAGE"
if [ -e {shlex.quote(user_root)} ] || [ -L {shlex.quote(user_root)} ]; then
  if [ ! -d {shlex.quote(user_root)} ] || [ -L {shlex.quote(user_root)} ]; then
    echo "[deploy] live user frontend must be a real directory" >&2
    exit 1
  fi
  : > "$ROLLBACK_STATE/user-had-live"
  mv {shlex.quote(user_root)} "$USER_BACKUP"
  USER_BACKED_UP=1
fi
mv "$USER_STAGE" {shlex.quote(user_root)}
USER_INSTALLED=1
stat -c '%d:%i' {shlex.quote(user_root)} > "$ROLLBACK_STATE/user-live-identity"
if [ -e {shlex.quote(admin_root)} ] || [ -L {shlex.quote(admin_root)} ]; then
  if [ ! -d {shlex.quote(admin_root)} ] || [ -L {shlex.quote(admin_root)} ]; then
    echo "[deploy] live admin frontend must be a real directory" >&2
    exit 1
  fi
  : > "$ROLLBACK_STATE/admin-had-live"
  mv {shlex.quote(admin_root)} "$ADMIN_BACKUP"
  ADMIN_BACKED_UP=1
fi
mv "$ADMIN_STAGE" {shlex.quote(admin_root)}
ADMIN_INSTALLED=1
stat -c '%d:%i' {shlex.quote(admin_root)} > "$ROLLBACK_STATE/admin-live-identity"
printf '%s\n' {shlex.quote(release_key)} > "$ROLLBACK_STATE/release-revision"
printf '%s\n' {shlex.quote(release_transaction)} > "$ROLLBACK_STATE/release-transaction"
if [ -e "$NGINX_SITE" ] || [ -L "$NGINX_SITE" ]; then
  if [ ! -f "$NGINX_SITE" ] || [ -L "$NGINX_SITE" ]; then
    echo "[deploy] live Nginx site must be a real file" >&2
    exit 1
  fi
  : > "$ROLLBACK_STATE/nginx-had-live"
  cp "$NGINX_SITE" "$NGINX_BACKUP"
  NGINX_HAD_LIVE=1
fi
NGINX_CHANGE_STARTED=1
install -m 644 "$NGINX_STAGE" "$NGINX_SITE"
rm -f "$NGINX_STAGE"
sha256sum "$NGINX_SITE" | awk '{{print $1}}' > "$ROLLBACK_STATE/nginx-deployed-sha256"
{nginx_test_command}
{nginx_reload_command}
curl -fsS -o /dev/null http://127.0.0.1:81/
curl -fsS -o /dev/null http://127.0.0.1:82/
: > "$ROLLBACK_STATE/cutover-complete"
trap - ERR
"""
        try:
            _stdout, _stderr, deploy_exit_code = remote.run(
                "bash -lc " + shlex.quote(cutover_script),
                check=False,
                timeout=3600,
            )
        except Exception as exc:
            raise CommandError(
                "Frontend cutover outcome is unknown because remote execution could not be observed"
            ) from exc
        if deploy_exit_code == 70:
            raise CommandError(
                "Frontend cutover failed and its automatic files/Nginx rollback did not complete"
            )
        if deploy_exit_code != 0:
            raise CommandError(
                "Frontend cutover failed; its prior files/Nginx state was restored"
            )

    frontend_rollback_script = f"""
set -Eeuo pipefail
ROLLBACK_STATE={shlex.quote(rollback_state)}
USER_BACKUP={shlex.quote(backup_root + '/user-web-' + timestamp)}
ADMIN_BACKUP={shlex.quote(backup_root + '/admin-web-' + timestamp)}
NGINX_SITE={shlex.quote(nginx_site_path)}
NGINX_BACKUP={shlex.quote(backup_root + '/nginx-full.conf.bak-' + timestamp)}
NGINX_FAILED={shlex.quote(release_root + '/nginx-full.conf.failed-' + timestamp)}
if [ ! -d "$ROLLBACK_STATE" ] || [ -L "$ROLLBACK_STATE" ] || [ ! -f "$ROLLBACK_STATE/cutover-complete" ]; then
  echo "[deploy] frontend rollback state is missing or incomplete" >&2
  exit 71
fi
if ! grep -Fqx -- {shlex.quote(release_key)} "$ROLLBACK_STATE/release-revision" \
  || ! grep -Fqx -- {shlex.quote(release_transaction)} "$ROLLBACK_STATE/release-transaction"; then
  echo "[deploy] frontend rollback transaction changed; refusing stale rollback" >&2
  exit 72
fi
if [ ! -d {shlex.quote(user_root)} ] || [ -L {shlex.quote(user_root)} ] \
  || [ "$(stat -c '%d:%i' {shlex.quote(user_root)})" != "$(tr -d '\r\n' < "$ROLLBACK_STATE/user-live-identity")" ]; then
  echo "[deploy] live user frontend changed; refusing stale rollback" >&2
  exit 72
fi
if [ ! -d {shlex.quote(admin_root)} ] || [ -L {shlex.quote(admin_root)} ] \
  || [ "$(stat -c '%d:%i' {shlex.quote(admin_root)})" != "$(tr -d '\r\n' < "$ROLLBACK_STATE/admin-live-identity")" ]; then
  echo "[deploy] live admin frontend changed; refusing stale rollback" >&2
  exit 72
fi
if [ -f "$ROLLBACK_STATE/user-had-live" ]; then
  test -d "$USER_BACKUP" && test ! -L "$USER_BACKUP"
elif [ -e "$USER_BACKUP" ] || [ -L "$USER_BACKUP" ]; then
  echo "[deploy] unexpected user frontend backup state" >&2
  exit 73
fi
if [ -f "$ROLLBACK_STATE/admin-had-live" ]; then
  test -d "$ADMIN_BACKUP" && test ! -L "$ADMIN_BACKUP"
elif [ -e "$ADMIN_BACKUP" ] || [ -L "$ADMIN_BACKUP" ]; then
  echo "[deploy] unexpected admin frontend backup state" >&2
  exit 73
fi
if [ ! -f "$NGINX_SITE" ] || [ -L "$NGINX_SITE" ] || [ ! -s "$ROLLBACK_STATE/nginx-deployed-sha256" ]; then
  echo "[deploy] live Nginx state changed; refusing stale rollback" >&2
  exit 74
fi
actual_nginx_sha=$(sha256sum "$NGINX_SITE" | awk '{{print $1}}')
expected_nginx_sha=$(tr -d '\r\n' < "$ROLLBACK_STATE/nginx-deployed-sha256")
if [ "$actual_nginx_sha" != "$expected_nginx_sha" ]; then
  echo "[deploy] live Nginx release changed; refusing stale rollback" >&2
  exit 74
fi
if [ -f "$ROLLBACK_STATE/nginx-had-live" ]; then
  test -f "$NGINX_BACKUP" && test ! -L "$NGINX_BACKUP"
fi
for failed_path in {shlex.quote(user_failed)} {shlex.quote(admin_failed)} "$NGINX_FAILED"; do
  if [ -e "$failed_path" ] || [ -L "$failed_path" ]; then
    echo "[deploy] frontend failed-release path collision" >&2
    exit 75
  fi
done
mv {shlex.quote(user_root)} {shlex.quote(user_failed)}
mv {shlex.quote(admin_root)} {shlex.quote(admin_failed)}
if [ -f "$ROLLBACK_STATE/user-had-live" ]; then mv "$USER_BACKUP" {shlex.quote(user_root)}; fi
if [ -f "$ROLLBACK_STATE/admin-had-live" ]; then mv "$ADMIN_BACKUP" {shlex.quote(admin_root)}; fi
cp "$NGINX_SITE" "$NGINX_FAILED"
if [ -f "$ROLLBACK_STATE/nginx-had-live" ]; then
  cp "$NGINX_BACKUP" "$NGINX_SITE"
else
  rm -f "$NGINX_SITE"
fi
{nginx_test_command}
{nginx_reload_command}
if [ -d {shlex.quote(user_root)} ]; then curl -fsS -o /dev/null http://127.0.0.1:81/; fi
if [ -d {shlex.quote(admin_root)} ]; then curl -fsS -o /dev/null http://127.0.0.1:82/; fi
rm -rf "$ROLLBACK_STATE"
"""
    frontend_rollback_cmd = "bash -lc " + shlex.quote(frontend_rollback_script)

    def rollback_after_release_gate():
        try:
            with RemoteHost("us-frontend-rollback", frontend, dry_run) as rollback_remote:
                _stdout, _stderr, exit_code = rollback_remote.run(
                    frontend_rollback_cmd,
                    check=False,
                    timeout=3600,
                )
        except Exception as exc:
            raise CommandError(
                "Post-deployment frontend rollback could not be executed"
            ) from exc
        if exit_code != 0:
            raise CommandError(
                "Post-deployment frontend files/Nginx rollback did not complete"
            )

    return DeploymentRollback("US frontend files and Nginx", rollback_after_release_gate)


def parse_args():
    parser = argparse.ArgumentParser(description="Deploy China backend and US frontends for production.")
    parser.add_argument("--config", default=".deploy.prod.json", help="Deployment config JSON relative to repo root or absolute path.")
    parser.add_argument("--target", choices=["all", "backend", "frontend"], default="all")
    parser.add_argument("--skip-frontend-build", action="store_true", help="Skip local frontend build steps during dry-run only.")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip HTTP smoke checks during dry-run only.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing them.")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Validate release inputs and Nginx origin transport without reading deploy credentials or changing state.",
    )
    parser.add_argument(
        "--nginx-config",
        help="Nginx config to validate with --preflight-only (defaults to the tracked US production config).",
    )
    parser.add_argument(
        "--migration-evidence",
        help="Absolute path to the operator-owned migration backup/restore evidence JSON.",
    )
    parser.add_argument(
        "--release-id",
        help="Immutable release identifier recorded in the migration evidence.",
    )
    parser.add_argument(
        "--release-revision",
        help="Immutable lowercase Git commit SHA recorded in the migration evidence.",
    )
    return parser.parse_args()


def rollback_completed_deployments(rollback_actions, original_error):
    failures = []
    for action in reversed(rollback_actions):
        try:
            action()
        except Exception:  # noqa: BLE001 - every remaining rollback must still be attempted
            failures.append(action.label)
    if failures:
        raise CommandError(
            "Release gate failed and automatic rollback did not complete for: "
            + ", ".join(failures)
        ) from original_error


def main():
    args = parse_args()
    if not args.dry_run and args.skip_frontend_build:
        raise ProductionPreflightError(
            "--skip-frontend-build is permitted only with --dry-run"
        )
    if not args.dry_run and args.skip_smoke:
        raise ProductionPreflightError(
            "--skip-smoke is permitted only with --dry-run"
        )
    if args.preflight_only:
        nginx_config = resolve_repo_path(args.nginx_config or DEFAULT_US_NGINX_CONFIG)
        run_release_preflight(include_backend=True, nginx_config=nginx_config)
        evidence = getattr(args, "migration_evidence", None)
        release_id = getattr(args, "release_id", None)
        release_revision = getattr(args, "release_revision", None)
        if len([value for value in (evidence, release_id, release_revision) if value]) not in {0, 3}:
            raise ProductionPreflightError(
                "--migration-evidence, --release-id and --release-revision must be supplied together"
            )
        if evidence and release_id and release_revision:
            actual_revision = validate_clean_release_revision()
            asserted_revision = _validated_release_revision(release_revision)
            if asserted_revision != actual_revision:
                raise ProductionPreflightError(
                    "--release-revision does not match the clean Git HEAD selected for preflight"
                )
            evidence_path = _operator_evidence_path(evidence)
            evidence_sha256_before = _sha256_file(evidence_path)
            validate_migration_manifest(
                production=True,
                evidence_file=evidence_path,
                release_id=release_id,
                release_revision=actual_revision,
            )
            if evidence_sha256_before != _sha256_file(evidence_path):
                raise ProductionPreflightError(
                    "migration evidence changed while it was being validated"
                )
            log("Production release preflight passed")
        else:
            log("Production release source preflight passed; migration evidence was not evaluated")
        return

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path
    config = load_config(config_path)
    release_revision = validate_clean_release_revision()
    asserted_revision = getattr(args, "release_revision", None)
    if asserted_revision is not None:
        asserted_revision = _validated_release_revision(asserted_revision)
        if asserted_revision != release_revision:
            raise ProductionPreflightError(
                "--release-revision does not match the clean Git HEAD selected for deployment"
            )
    log(f"Release revision: {release_revision}")

    include_backend = args.target in {"all", "backend"}
    release_id = None
    migration_evidence_sha256 = None
    nginx_config = None
    if args.target in {"all", "frontend"}:
        frontend = config["us_frontend"]
        nginx_config = resolve_repo_path(
            frontend.get("nginx_config_source", str(DEFAULT_US_NGINX_CONFIG))
        )
    run_release_preflight(include_backend=include_backend, nginx_config=nginx_config)
    if include_backend:
        evidence = getattr(args, "migration_evidence", None)
        release_id = getattr(args, "release_id", None)
        evidence_path = _operator_evidence_path(evidence) if evidence else None
        evidence_sha256_before = _sha256_file(evidence_path) if evidence_path else None
        validate_migration_manifest(
            production=True,
            evidence_file=evidence_path,
            release_id=release_id,
            release_revision=release_revision,
        )
        migration_evidence_sha256 = _sha256_file(evidence_path) if evidence_path else None
        if evidence_sha256_before != migration_evidence_sha256:
            raise ProductionPreflightError(
                "migration evidence changed while it was being validated"
            )

    rollback_actions = []
    try:
        if args.target in {"all", "backend"}:
            backend_rollback = deploy_backend(
                config,
                dry_run=args.dry_run,
                deploy_mode=args.target,
                release_revision=release_revision,
                release_id=release_id,
                migration_evidence_sha256=migration_evidence_sha256,
                verify_local_source=True,
            )
            if backend_rollback is not None:
                rollback_actions.append(backend_rollback)

        if args.target in {"all", "frontend"}:
            frontend_rollback = deploy_frontend(
                config,
                skip_frontend_build=args.skip_frontend_build,
                dry_run=args.dry_run,
                release_revision=release_revision,
                verify_local_source=True,
            )
            if frontend_rollback is not None:
                rollback_actions.append(frontend_rollback)

        if not args.skip_smoke:
            run_smoke_checks(config, args.target, dry_run=args.dry_run)
    except BaseException as exc:
        if rollback_actions and not args.dry_run:
            rollback_completed_deployments(rollback_actions, exc)
        raise

    log("Done")


if __name__ == "__main__":
    try:
        main()
    except (CommandError, FileNotFoundError, RuntimeError, urllib.error.URLError) as exc:
        log(f"FAILED: {exc}")
        sys.exit(1)
