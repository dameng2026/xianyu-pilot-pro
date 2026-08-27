import shutil
import hashlib
import os
import shlex
import socket
import socketserver
import subprocess
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest

from test_prod_deploy import prod_deploy


REPO_ROOT = Path(__file__).resolve().parents[2]
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


def _find_usable_bash():
    candidates = []
    if Path("C:/Program Files/Git/bin/bash.exe").is_file():
        candidates.append("C:/Program Files/Git/bin/bash.exe")
    if shutil.which("bash"):
        candidates.append(shutil.which("bash"))
    for candidate in candidates:
        try:
            probe = subprocess.run(
                [candidate, "-c", "printf bash-ok"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if probe.returncode == 0 and probe.stdout == "bash-ok":
            return candidate
    return None


BASH = _find_usable_bash()


def _production_resource_env() -> dict[str, str]:
    values: dict[str, str] = {"PROMETHEUS_RETENTION_SIZE": "20GB"}
    for prefix in (
        "MYSQL",
        "REDIS",
        "POSTGRES",
        "CORE_API",
        "AUTOMATION_API",
        "AUTOMATION_WORKER",
        "CRAWLER_API",
        "CRAWLER_WORKER",
        "USER_WEB",
        "ADMIN_WEB",
        "BLACKBOX",
        "ALERTMANAGER",
        "PROMETHEUS",
        "GRAFANA",
    ):
        values[f"{prefix}_MEMORY_LIMIT_BYTES"] = "1073741824"
        values[f"{prefix}_CPUS"] = "1.0"
        values[f"{prefix}_PIDS_LIMIT"] = "256"
    return values


def _bash_absolute_path(path: Path) -> str:
    if os.name != "nt":
        return path.resolve().as_posix()
    completed = subprocess.run(
        [BASH, "-lc", 'cygpath -u "$1"', "--", str(path.resolve())],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _chmod_owner_only_or_skip(path: Path) -> str:
    """Create a real 0600 fixture or skip where the host cannot model POSIX modes."""

    if os.name == "nt":
        cygpath = subprocess.run(
            [BASH, "-c", "command -v cygpath >/dev/null"],
            check=False,
            capture_output=True,
            text=True,
        )
        if cygpath.returncode != 0:
            pytest.skip("Git Bash cygpath is required for permission contracts")
    bash_path = _bash_absolute_path(path)
    subprocess.run(
        [BASH, "-c", 'chmod 600 -- "$1"', "--", bash_path],
        check=True,
        capture_output=True,
        text=True,
    )
    mode = subprocess.run(
        [BASH, "-c", 'stat -c "%a" -- "$1"', "--", bash_path],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if mode not in {"400", "600"}:
        if os.name == "nt":
            pytest.skip("Windows filesystem cannot model owner-only POSIX permissions")
        pytest.fail(f"owner-only fixture permissions were not applied: {mode}")
    return bash_path


def _prepare_monitoring_secret_or_skip(path: Path) -> tuple[str, str]:
    """Model the production bind-mount contract for a non-root container."""

    if os.name == "nt":
        cygpath = subprocess.run(
            [BASH, "-c", "command -v cygpath >/dev/null"],
            check=False,
            capture_output=True,
        )
        if cygpath.returncode != 0:
            pytest.skip("Git Bash cygpath is required for permission contracts")
    bash_path = _bash_absolute_path(path)
    bash_parent = _bash_absolute_path(path.parent)
    try:
        subprocess.run(
            [BASH, "-c", 'chmod 750 -- "$1" && chmod 640 -- "$2"', "--", bash_parent, bash_path],
            check=True,
            capture_output=True,
        )
        metadata = subprocess.run(
            [
                BASH,
                "-c",
                'printf "%s %s %s %s" "$(stat -c %a -- "$1")" "$(stat -c %g -- "$1")" '
                '"$(stat -c %a -- "$2")" "$(stat -c %g -- "$2")"',
                "--",
                bash_parent,
                bash_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip().split()
    except subprocess.CalledProcessError:
        if os.name == "nt":
            pytest.skip("Windows filesystem cannot model monitoring secret POSIX permissions")
        raise
    if len(metadata) != 4 or metadata[0] != "750" or metadata[2] != "640" or metadata[1] != metadata[3]:
        if os.name == "nt":
            pytest.skip("Windows filesystem cannot model monitoring secret POSIX ownership")
        pytest.fail(f"monitoring secret permissions were not applied: {metadata}")
    return bash_path, metadata[3]


def _git_says_ignored(repo: Path, relative_path: str) -> bool:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    completed = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "--no-index", "-q", relative_path],
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for ignore contract")
def test_gitignore_blocks_local_secrets_captures_and_runtime_artifacts(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    shutil.copyfile(REPO_ROOT / ".gitignore", repo / ".gitignore")
    subprocess.run(["git", "init", "-q", str(repo)], check=True)

    sensitive_paths = [
        ".env",
        ".env.production",
        ".deploy.prod.json",
        "captures/login.har",
        "runtime/session_token.txt",
        "runtime/cookies.json",
        "runtime/private.key",
        "runtime/client.pfx",
        "runtime/migration-evidence.json",
        ".npm-cache/cache-entry",
        ".npm-bootstrap-cache/cache-entry",
        ".pnpm-store/cache-entry",
        ".tools/node/tool.exe",
        ".uv-cache/cache-entry",
        ".uv-tools/tool-entry",
        ".uv-tools-bin/tool-entry",
        "logs/service.log",
        "temp/release.tmp",
    ]
    for relative_path in sensitive_paths:
        assert _git_says_ignored(repo, relative_path), relative_path

    assert not _git_says_ignored(repo, ".env.production.example")
    assert not _git_says_ignored(repo, ".deploy.prod.example.json")
    assert not _git_says_ignored(repo, "db/migration-evidence.example.json")


def test_dev_start_never_terminates_port_owners_and_has_read_only_validation_mode():
    script = (REPO_ROOT / "dev-start.ps1").read_text(encoding="utf-8-sig")

    assert "Stop-Process" not in script
    assert "[switch]$ValidateOnly" in script
    assert "another checkout" in script.lower()
    assert "will not terminate" in script.lower()


def test_dev_start_uses_the_pinned_fail_closed_node_and_maven_toolchains():
    script = (REPO_ROOT / "dev-start.ps1").read_text(encoding="utf-8-sig")

    assert (REPO_ROOT / ".node-version").read_text(encoding="utf-8").strip() == "24.18.0"
    assert "24.18.0" in script
    assert "11.16.0" in script
    assert "npm.cmd ci --registry=https://registry.npmjs.org --no-audit --no-fund --strict-allow-scripts" in script
    assert "npm install" not in script
    assert "pnpm" not in script.lower()
    assert "Invoke-Expression" not in script
    assert "Start-Job" not in script
    assert "Test-DependencyRefreshAllowed" in script
    assert "--index-url https://pypi.org/simple --only-binary=:all:" in script
    assert ".\\mvnw.cmd" in script
    assert "mvn package" not in script
    assert ".\\.venv\\Scripts\\python.exe run-fast.py" in script
    assert "Art Design Pro" not in script
    assert "闲鱼助手管理后台" in script

    for launcher_name in ("start.bat", "dev-start.bat"):
        launcher = (REPO_ROOT / launcher_name).read_text(encoding="utf-8-sig").lower()
        assert 'dev-start.ps1' in launcher
        assert 'pip install' not in launcher
        assert 'npm install' not in launcher


class _CrawlerIdentityHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        payload = b'{"status":"ok","service":"crawler-service"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, _format, *_args):
        return


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required for launcher contract")
def test_dev_start_rejects_other_checkout_listener_without_terminating_it():
    server = socketserver.TCPServer(("127.0.0.1", 0), _CrawlerIdentityHandler)
    port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        completed = subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(REPO_ROOT / "dev-start.ps1"),
                "-ValidateOnly",
                "-ValidationService",
                "crawler-service",
                "-ValidationPort",
                str(port),
                "-NoPause",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )

        output = (completed.stdout + completed.stderr).lower()
        assert completed.returncode == 2, output
        assert f"port {port}" in output
        assert "another checkout" in output
        assert "will not terminate" in output
        assert "startup aborted before changing infrastructure" in output
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=3) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(POWERSHELL is None, reason="PowerShell is required for launcher contract")
def test_dev_start_read_only_validation_accepts_a_free_service_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]

    completed = subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(REPO_ROOT / "dev-start.ps1"),
            "-ValidateOnly",
            "-ValidationService",
            "crawler-service",
            "-ValidationPort",
            str(port),
            "-NoPause",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = (completed.stdout + completed.stderr).lower()
    assert completed.returncode == 0, output
    assert f"port {port} is free" in output
    assert "development port ownership preflight passed" in output


def test_blue_green_entrypoint_is_an_explicit_fail_fast_not_a_fake_deploy():
    script = (REPO_ROOT / "scripts" / "blue-green-deploy.sh").read_text(encoding="utf-8")

    assert "UNSUPPORTED" in script
    assert "exit 64" in script
    assert "fixed container_name" in script
    assert "host ports" in script
    assert "scripts/prod_deploy.py" in script
    assert "docker compose" not in script
    assert "|| true" not in script


@pytest.mark.skipif(BASH is None, reason="Bash is required for entrypoint runtime contract")
def test_blue_green_entrypoint_exits_unsupported_before_any_deploy_command():
    completed = subprocess.run(
        [BASH, str(REPO_ROOT / "scripts" / "blue-green-deploy.sh")],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode == 64, output
    assert "UNSUPPORTED" in output
    assert "No deployment commands were run" in output


def test_compose_files_disclose_single_stack_release_semantics():
    base = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    production = (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    combined = (base + "\n" + production).lower()
    assert "single-stack" in combined
    assert "not blue/green" in combined
    assert "scripts/prod_deploy.py" in combined


def test_production_compose_requires_redis_authentication_and_persistence():
    base = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    production = (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    env_example = (REPO_ROOT / ".env.production.example").read_text(encoding="utf-8")

    assert "--requirepass" in base
    assert "--requirepass" in production
    assert "REDIS_PASSWORD" in base
    assert "${REDIS_PASSWORD:?REDIS_PASSWORD must be set}" in production
    assert "redis_data:/data" in base
    assert "condition: service_healthy" in base
    assert "REDIS_PASSWORD=replace-with-strong-redis-password-32chars" in env_example


def test_production_compose_rejects_all_development_database_credentials():
    production = (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    required_interpolations = (
        "${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD must be set}",
        "${MYSQL_APP_USER:?MYSQL_APP_USER must be set}",
        "${MYSQL_APP_PASSWORD:?MYSQL_APP_PASSWORD must be set}",
        "${CRAWLER_DB:?CRAWLER_DB must be set}",
        "${CRAWLER_DB_USER:?CRAWLER_DB_USER must be set}",
        "${CRAWLER_DB_PASSWORD:?CRAWLER_DB_PASSWORD must be set}",
        "${REDIS_PASSWORD:?REDIS_PASSWORD must be set}",
    )
    for interpolation in required_interpolations:
        assert interpolation in production

    assert "dev-only" not in production
    assert "crawler_pass" not in production
    assert "MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-root}" not in production


def test_production_release_is_fail_closed_on_migration_and_recovery_evidence():
    production = (REPO_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")
    legacy_preflight = (REPO_ROOT / "scripts/production-preflight.sh").read_text(encoding="utf-8")
    deploy = (REPO_ROOT / "scripts/prod_deploy.py").read_text(encoding="utf-8")
    wrapper = (REPO_ROOT / "scripts/deploy-prod.ps1").read_text(encoding="utf-8")
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert production.count('SCHEMA_RUNTIME_MUTATIONS_ENABLED: "false"') == 5
    assert "DATABASE_MIGRATION_EVIDENCE_FILE" in legacy_preflight
    assert "RELEASE_ID" in legacy_preflight
    assert "validate_migrations.py" in legacy_preflight
    assert "--production" in legacy_preflight
    assert "--migration-evidence" in deploy
    assert "--release-id" in deploy
    assert "validate_migration_manifest" in deploy
    assert "MigrationEvidence" in wrapper
    assert "ReleaseId" in wrapper
    assert "python scripts/validate_migrations.py" in ci


def test_migration_manifest_tracks_all_three_databases_and_quarantines_duplicate_v1_1():
    manifest = (REPO_ROOT / "db/migrations-manifest.json").read_text(encoding="utf-8")
    core_migrations = REPO_ROOT / "apps/core-api/src/main/resources/db/migration"

    assert '"id": "core_mysql"' in manifest
    assert '"id": "automation_mysql"' in manifest
    assert '"id": "crawler_postgres"' in manifest
    assert '"immutableAfterRelease": true' in manifest
    assert '"productionRuntimeSchemaMutation": false' in manifest
    assert len(list(core_migrations.glob("V1.1__*.sql"))) == 1
    assert "LEGACY_V1.1__add_goods_sync_fields.sql.disabled" in manifest

    digest = hashlib.sha256(manifest.encode("utf-8")).hexdigest()
    crawler_migrator = (REPO_ROOT / "apps/crawler-service/src/migrate.ts").read_text(encoding="utf-8")
    assert f"REVIEWED_MANIFEST_SHA256 = '{digest}'" in crawler_migrator


def test_legacy_public_http_origin_config_is_explicitly_blocked():
    path = REPO_ROOT / "deploy/nginx/xianyupilot-ssl.conf"
    text = path.read_text(encoding="utf-8")

    with pytest.raises(prod_deploy.ProductionPreflightError, match="origin hop"):
        prod_deploy.validate_nginx_transport_security(path)

    assert "SECURITY BLOCKER" in text
    assert "proxy_ssl_verify on" in text
    assert "mTLS" in text
    assert "VPN" in text


def test_tracked_us_origin_routes_only_over_private_or_verified_paths():
    path = REPO_ROOT / "deploy/nginx/us-nginx-full.conf"
    text = path.read_text(encoding="utf-8")

    # No public plaintext HTTP and no unverified HTTPS origin anywhere.
    prod_deploy.validate_nginx_transport_security(path)
    # The managed loopback SSH tunnel service template stays valid for
    # deployments that prefer it over the WireGuard private path.
    prod_deploy.validate_origin_tunnel_service_template()

    assert "upstream xianyu_backend" in text
    assert "server 10.0.0.1:18080;" in text
    # Internal frontend listeners must stay loopback-only.
    assert "listen 127.0.0.1:81;" in text
    assert "listen 127.0.0.1:82;" in text
    assert "\n    listen 81;" not in text
    assert "\n    listen 82;" not in text
    # Every proxied location must forward a trace id.
    assert text.count("proxy_set_header X-Request-ID") == (
        text.count("proxy_pass http://xianyu_backend")
        + text.count("proxy_pass https://backend.example.com")
    )


def test_tls_terminated_public_vhosts_forward_the_real_client_scheme():
    text = (REPO_ROOT / "deploy" / "nginx" / "us-nginx-full.conf").read_text(
        encoding="utf-8"
    )
    user_public = text.split("server_name www.example.com;", 1)[1].split(
        "server_name admin.example.com;", 1
    )[0]
    admin_public = text.split("server_name admin.example.com;", 1)[1].split(
        "listen 127.0.0.1:81;", 1
    )[0]

    assert "X-Forwarded-Proto $scheme" not in user_public
    assert "X-Forwarded-Proto $scheme" not in admin_public
    assert user_public.count("X-Forwarded-Proto https") >= 5
    assert admin_public.count("X-Forwarded-Proto https") >= 2
    assert "geo $from_local_tls_terminator" in text
    assert "127.0.0.1 1;" in text
    assert "::1 1;" in text
    # Public plaintext HTTP stays reachable for ACME challenges only.
    assert "~^0:http:/\\.well-known/acme-challenge/ 0;" in text
    # www, admin and api vhosts all force-redirect plaintext to HTTPS.
    assert text.count("return 308 https://$host$request_uri;") == 3


def test_frontend_deploy_fails_closed_until_managed_origin_tunnel_is_healthy():
    text = (REPO_ROOT / "scripts" / "prod_deploy.py").read_text(encoding="utf-8")

    active_check = "systemctl is-active --quiet"
    health_check = "origin_tunnel_health_url"
    first_upload = "remote.upload(nginx_config_path"
    assert active_check in text
    assert health_check in text
    assert text.index(active_check) < text.index(first_upload)


def test_release_smoke_failures_do_not_dump_login_response_bodies():
    text = (REPO_ROOT / "scripts" / "prod_deploy.py").read_text(encoding="utf-8")

    assert "text[:200]" not in text
    assert "failed with application code" in text


def test_local_login_smoke_requires_operator_supplied_test_credentials():
    text = (REPO_ROOT / "scripts" / "tests" / "test-local-navigation-home.mjs").read_text(
        encoding="utf-8"
    )

    assert "TEST_USER_USERNAME" in text
    assert "TEST_USER_PASSWORD" in text
    assert "password: '123456'" not in text





def test_legacy_production_preflight_runs_shared_transport_gate_before_loading_env():
    script = (REPO_ROOT / "scripts" / "production-preflight.sh").read_text(
        encoding="utf-8"
    )

    shared_gate_position = script.index("--preflight-only")
    env_load_position = script.index('done < "$ENV_FILE"')
    assert shared_gate_position < env_load_position
    assert 'source "$ENV_FILE"' not in script
    assert "Production env file must use owner-only" in script
    assert "Production env file contains undocumented key" in script
    assert ".env.production.example" in script
    assert "docker compose is required for production config validation" in script
    assert "--nginx-config" in script
    assert "|| true" not in script
    assert "/tmp/xianyu-compose.rendered.yml" not in script
    assert "config --quiet" in script
    assert "-f docker-compose.yml" in script
    assert "-f docker-compose.prod.yml" in script
    assert "-f docker-compose.monitoring.yml" in script
    assert "--profile monitoring" in script
    assert "OPS_METRICS_TOKEN_FILE does not match OPS_METRICS_TOKEN" in script
    assert "must contain exactly one line" in script
    assert "must not point to a symbolic link" in script
    assert "must use 0440 or 0640 permissions for the dedicated monitoring group" in script
    assert "parent directory must use 0750 permissions" in script
    assert "group must match MONITORING_SECRET_GID" in script
    assert "owned by root or the deployment operator" in script
    assert 'loaded_env_values[$key]="$value"' in script
    assert 'lowered_value="${value,,}"' in script
    assert 'printf -v "$key"' not in script
    assert 'printf -v "$required_key"' in script
    assert "arbitrary dotenv keys" in script
    assert "must use URL-safe ASCII without dotenv or shell metacharacters" in script
    assert "MYSQL_APP_USER must be a least-privilege application identifier" in script
    assert "Production credentials must be distinct" in script
    assert 'EXPECTED_RELEASE_REVISION="${3:-}"' in script
    assert 'EXPECTED_RELEASE_ID="${4:-}"' in script
    assert 'EXPECTED_MIGRATION_EVIDENCE_SHA256="${5:-}"' in script
    assert '"$RELEASE_REVISION" == "$EXPECTED_RELEASE_REVISION"' in script
    assert '"$RELEASE_ID" == "$EXPECTED_RELEASE_ID"' in script
    assert '"$actual_migration_evidence_sha256" == "$EXPECTED_MIGRATION_EVIDENCE_SHA256"' in script
    assert '"$verified_migration_evidence_sha256" == "$EXPECTED_MIGRATION_EVIDENCE_SHA256"' in script
    assert "does not match the Git revision selected by the deploy entrypoint" in script
    assert "Remote migration evidence does not match the locally validated evidence" in script
    for required in (
        "MYSQL_ROOT_PASSWORD",
        "MYSQL_APP_USER",
        "MYSQL_APP_PASSWORD",
        "CRAWLER_DB",
        "CRAWLER_DB_USER",
        "CRAWLER_DB_PASSWORD",
        "REDIS_PASSWORD",
        "OPS_METRICS_TOKEN",
        "OPS_METRICS_TOKEN_FILE",
        "ALERTMANAGER_WEBHOOK_URL_FILE",
        "MONITORING_SECRET_GID",
        "GRAFANA_ADMIN_PASSWORD_FILE",
        "GRAFANA_ROOT_URL",
        "IMAGE_PROXY_ALLOWED_HOSTS",
        "AI_PROVIDER_ALLOWED_HOSTS",
        "ADMIN_CORS_ALLOWED_ORIGINS",
        "USER_CORS_ALLOWED_ORIGINS",
        "CRAWLER_CORS_ALLOWED_ORIGINS",
        "JWT_EXPIRE_SECONDS",
        "MEDIA_COOKIE_SECURE",
        "MEDIA_SESSION_MAX_AGE_SECONDS",
        "UPLOAD_RATE_LIMIT_REQUESTS",
        "UPLOAD_RATE_LIMIT_WINDOW_SECONDS",
        "UPLOAD_MAX_CONCURRENT_PER_TENANT",
        "UPLOAD_MAX_CONCURRENT_GLOBAL",
        "UPLOAD_RETENTION_DAYS",
    ):
        assert required in script
    assert "UPLOAD_MAX_CONCURRENT_GLOBAL must be at least the tenant limit and at most 1000" in script
    assert "Upload rate, concurrency, and retention limits passed" in script


@pytest.mark.skipif(BASH is None, reason="Bash is required for legacy preflight contract")
def test_legacy_preflight_rejects_remote_env_revision_different_from_deploy_head(tmp_path):
    coreutils = subprocess.run(
        [BASH, "-c", "command -v chmod >/dev/null && command -v stat >/dev/null"],
        check=False,
        capture_output=True,
        text=True,
    )
    if coreutils.returncode != 0:
        pytest.skip("Bash coreutils are required for the executable preflight contract")

    revision = "c" * 40
    expected_revision = "d" * 40
    long_secret = "A" * 40
    env_values = {
        **_production_resource_env(),
        "RELEASE_ID": "release-20260711-01",
        "RELEASE_REVISION": revision,
        "DATABASE_MIGRATION_EVIDENCE_FILE": "/secure/migration-evidence.json",
        "MYSQL_ROOT_PASSWORD": long_secret,
        "MYSQL_APP_USER": "xianyu_app",
        "MYSQL_APP_PASSWORD": long_secret,
        "CRAWLER_DB": "xianyu_crawler",
        "CRAWLER_DB_USER": "xianyu_crawler",
        "CRAWLER_DB_PASSWORD": long_secret,
        "REDIS_PASSWORD": long_secret,
        "ADMIN_JWT_SECRET": long_secret,
        "COOKIE_CRYPTO_SECRET": long_secret,
        "INTERNAL_API_TOKEN": long_secret,
        "OPS_METRICS_TOKEN": long_secret,
        "OPS_METRICS_TOKEN_FILE": "/secure/ops-token",
        "ALERTMANAGER_WEBHOOK_URL_FILE": "/secure/alertmanager-webhook",
        "MONITORING_SECRET_GID": "64000",
        "GRAFANA_ADMIN_PASSWORD_FILE": "/secure/grafana-admin-password",
        "GRAFANA_ROOT_URL": "https://grafana.example.com",
        "IMAGE_PROXY_ALLOWED_HOSTS": "images.example.com",
        "AI_PROVIDER_ALLOWED_HOSTS": "api.provider.example.com",
        "JWT_EXPIRE_SECONDS": "900",
        "MEDIA_COOKIE_SECURE": "true",
        "MEDIA_SESSION_MAX_AGE_SECONDS": "600",
        "UPLOAD_TENANT_QUOTA_BYTES": "1073741824",
        "UPLOAD_GLOBAL_QUOTA_BYTES": "107374182400",
        "UPLOAD_RATE_LIMIT_REQUESTS": "30",
        "UPLOAD_RATE_LIMIT_WINDOW_SECONDS": "60",
        "UPLOAD_MAX_CONCURRENT_PER_TENANT": "2",
        "UPLOAD_MAX_CONCURRENT_GLOBAL": "8",
        "UPLOAD_RETENTION_DAYS": "365",
        "JWT_ISSUER": "xianyupilot",
        "JWT_AUDIENCE": "xianyupilot-users",
        "ADMIN_CORS_ALLOWED_ORIGINS": "https://admin.example.com",
        "USER_CORS_ALLOWED_ORIGINS": "https://www.example.com",
        "CRAWLER_CORS_ALLOWED_ORIGINS": "https://crawler.example.com",
        "BACKEND_PORT": "18080",
        "USER_WEB_PORT": "81",
        "ADMIN_WEB_PORT": "82",
    }
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "".join(f"{key}={value}\n" for key, value in env_values.items()),
        encoding="utf-8",
    )
    env_file_for_bash = _chmod_owner_only_or_skip(env_file)
    nginx_config = tmp_path / "secure-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHON_BIN"] = "/usr/bin/true"

    completed = subprocess.run(
        [
            BASH,
            "scripts/production-preflight.sh",
            env_file_for_bash,
            _bash_absolute_path(nginx_config),
            expected_revision,
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0, output
    assert "does not match the Git revision selected by the deploy entrypoint" in output
    assert "Migration manifest or backup/restore evidence" not in output


@pytest.mark.skipif(BASH is None, reason="Bash is required for legacy preflight contract")
def test_legacy_preflight_rejects_remote_evidence_bytes_different_from_local_binding(
    tmp_path,
):
    required_commands = (
        "command -v chmod >/dev/null && command -v stat >/dev/null "
        "&& command -v sha256sum >/dev/null"
    )
    if os.name == "nt":
        required_commands += " && command -v cygpath >/dev/null"
    coreutils = subprocess.run(
        [
            BASH,
            "-c",
            required_commands,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if coreutils.returncode != 0 and os.name == "nt":
        pytest.skip("Git Bash coreutils and cygpath are required")
    if coreutils.returncode != 0:
        pytest.skip("Bash coreutils are required")

    revision = "c" * 40
    release_id = "release-20260711-01"
    long_secret = "A" * 40
    evidence = tmp_path / "migration-evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    metrics_token = tmp_path / "ops-token"
    metrics_token.write_text(long_secret + "\n", encoding="utf-8")
    incident_webhook = tmp_path / "alertmanager-webhook"
    incident_webhook.write_text("https://alerts.example.com/xianyupilot\n", encoding="utf-8")
    grafana_password = tmp_path / "grafana-admin-password"
    grafana_password.write_text("B" * 40 + "\n", encoding="utf-8")
    _chmod_owner_only_or_skip(evidence)
    metrics_token_path, monitoring_gid = _prepare_monitoring_secret_or_skip(metrics_token)
    incident_webhook_path, incident_gid = _prepare_monitoring_secret_or_skip(incident_webhook)
    grafana_password_path, grafana_gid = _prepare_monitoring_secret_or_skip(grafana_password)
    assert incident_gid == monitoring_gid == grafana_gid

    env_values = {
        **_production_resource_env(),
        "RELEASE_ID": release_id,
        "RELEASE_REVISION": revision,
        "DATABASE_MIGRATION_EVIDENCE_FILE": _bash_absolute_path(evidence),
        "MYSQL_ROOT_PASSWORD": long_secret,
        "MYSQL_APP_USER": "xianyu_app",
        "MYSQL_APP_PASSWORD": long_secret,
        "CRAWLER_DB": "xianyu_crawler",
        "CRAWLER_DB_USER": "xianyu_crawler",
        "CRAWLER_DB_PASSWORD": long_secret,
        "REDIS_PASSWORD": long_secret,
        "ADMIN_JWT_SECRET": long_secret,
        "COOKIE_CRYPTO_SECRET": long_secret,
        "INTERNAL_API_TOKEN": long_secret,
        "OPS_METRICS_TOKEN": long_secret,
        "OPS_METRICS_TOKEN_FILE": metrics_token_path,
        "ALERTMANAGER_WEBHOOK_URL_FILE": incident_webhook_path,
        "MONITORING_SECRET_GID": monitoring_gid,
        "GRAFANA_ADMIN_PASSWORD_FILE": grafana_password_path,
        "GRAFANA_ROOT_URL": "https://grafana.example.com",
        "IMAGE_PROXY_ALLOWED_HOSTS": "images.example.com",
        "AI_PROVIDER_ALLOWED_HOSTS": "api.provider.example.com",
        "JWT_EXPIRE_SECONDS": "900",
        "MEDIA_COOKIE_SECURE": "true",
        "MEDIA_SESSION_MAX_AGE_SECONDS": "600",
        "UPLOAD_TENANT_QUOTA_BYTES": "1073741824",
        "UPLOAD_GLOBAL_QUOTA_BYTES": "107374182400",
        "UPLOAD_RATE_LIMIT_REQUESTS": "30",
        "UPLOAD_RATE_LIMIT_WINDOW_SECONDS": "60",
        "UPLOAD_MAX_CONCURRENT_PER_TENANT": "2",
        "UPLOAD_MAX_CONCURRENT_GLOBAL": "8",
        "UPLOAD_RETENTION_DAYS": "365",
        "JWT_ISSUER": "xianyupilot",
        "JWT_AUDIENCE": "xianyupilot-users",
        "ADMIN_CORS_ALLOWED_ORIGINS": "https://admin.example.com",
        "USER_CORS_ALLOWED_ORIGINS": "https://www.example.com",
        "CRAWLER_CORS_ALLOWED_ORIGINS": "https://crawler.example.com",
        "BACKEND_PORT": "18080",
        "USER_WEB_PORT": "81",
        "ADMIN_WEB_PORT": "82",
    }
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "".join(f"{key}={value}\n" for key, value in env_values.items()),
        encoding="utf-8",
    )
    _chmod_owner_only_or_skip(env_file)
    nginx_config = tmp_path / "secure-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )

    environment = dict(os.environ)
    environment["PYTHON_BIN"] = "/usr/bin/true"
    completed = subprocess.run(
        [
            BASH,
            "scripts/production-preflight.sh",
            _bash_absolute_path(env_file),
            _bash_absolute_path(nginx_config),
            revision,
            release_id,
            "0" * 64,
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0, output
    assert "Remote migration evidence does not match the locally validated evidence" in output
    assert "Migration manifest or backup/restore evidence validation failed" not in output


@pytest.mark.skipif(BASH is None, reason="Bash is required for legacy preflight contract")
def test_legacy_preflight_rejects_an_unbounded_production_resource(tmp_path):
    long_secret = "A" * 40
    secret_dir = tmp_path / "monitoring-secrets"
    secret_dir.mkdir()
    metrics_token = secret_dir / "ops-token"
    incident_webhook = secret_dir / "alertmanager-webhook"
    grafana_password = secret_dir / "grafana-admin-password"
    metrics_token.write_text("H" * 40 + "\n", encoding="utf-8")
    incident_webhook.write_text("https://alerts.example.com/xianyupilot\n", encoding="utf-8")
    grafana_password.write_text("I" * 40 + "\n", encoding="utf-8")
    metrics_path, monitoring_gid = _prepare_monitoring_secret_or_skip(metrics_token)
    webhook_path, webhook_gid = _prepare_monitoring_secret_or_skip(incident_webhook)
    grafana_path, grafana_gid = _prepare_monitoring_secret_or_skip(grafana_password)
    if not 100 <= int(monitoring_gid) <= 65533:
        pytest.skip("The test runner does not have an eligible monitoring secret group")
    assert monitoring_gid == webhook_gid == grafana_gid

    env_values = {
        **_production_resource_env(),
        "RELEASE_ID": "release-20260711-01",
        "RELEASE_REVISION": "c" * 40,
        "DATABASE_MIGRATION_EVIDENCE_FILE": "/secure/migration-evidence.json",
        "MYSQL_ROOT_PASSWORD": long_secret,
        "MYSQL_APP_USER": "xianyu_app",
        "MYSQL_APP_PASSWORD": "B" * 40,
        "CRAWLER_DB": "xianyu_crawler",
        "CRAWLER_DB_USER": "xianyu_crawler",
        "CRAWLER_DB_PASSWORD": "C" * 40,
        "REDIS_PASSWORD": "D" * 40,
        "ADMIN_JWT_SECRET": "E" * 40,
        "COOKIE_CRYPTO_SECRET": "F" * 40,
        "INTERNAL_API_TOKEN": "G" * 40,
        "OPS_METRICS_TOKEN": "H" * 40,
        "OPS_METRICS_TOKEN_FILE": metrics_path,
        "ALERTMANAGER_WEBHOOK_URL_FILE": webhook_path,
        "GRAFANA_ADMIN_PASSWORD_FILE": grafana_path,
        "MONITORING_SECRET_GID": monitoring_gid,
        "GRAFANA_ROOT_URL": "https://grafana.example.com",
        "IMAGE_PROXY_ALLOWED_HOSTS": "images.example.com",
        "AI_PROVIDER_ALLOWED_HOSTS": "api.provider.example.com",
        "JWT_EXPIRE_SECONDS": "900",
        "MEDIA_COOKIE_SECURE": "true",
        "MEDIA_SESSION_MAX_AGE_SECONDS": "600",
        "UPLOAD_TENANT_QUOTA_BYTES": "1073741824",
        "UPLOAD_GLOBAL_QUOTA_BYTES": "107374182400",
        "UPLOAD_RATE_LIMIT_REQUESTS": "30",
        "UPLOAD_RATE_LIMIT_WINDOW_SECONDS": "60",
        "UPLOAD_MAX_CONCURRENT_PER_TENANT": "2",
        "UPLOAD_MAX_CONCURRENT_GLOBAL": "8",
        "UPLOAD_RETENTION_DAYS": "365",
        "JWT_ISSUER": "xianyupilot",
        "JWT_AUDIENCE": "xianyupilot-users",
        "ADMIN_CORS_ALLOWED_ORIGINS": "https://admin.example.com",
        "USER_CORS_ALLOWED_ORIGINS": "https://www.example.com",
        "CRAWLER_CORS_ALLOWED_ORIGINS": "https://crawler.example.com",
        "BACKEND_PORT": "18080",
        "USER_WEB_PORT": "81",
        "ADMIN_WEB_PORT": "82",
    }
    env_values["MYSQL_MEMORY_LIMIT_BYTES"] = "0"
    env_file = tmp_path / ".env.production"
    env_file.write_text(
        "".join(f"{key}={value}\n" for key, value in env_values.items()),
        encoding="utf-8",
    )
    env_path = _chmod_owner_only_or_skip(env_file)
    nginx_config = tmp_path / "secure-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHON_BIN"] = "/usr/bin/true"

    completed = subprocess.run(
        [
            BASH,
            "scripts/production-preflight.sh",
            env_path,
            _bash_absolute_path(nginx_config),
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0, output
    assert "MYSQL_MEMORY_LIMIT_BYTES must be a canonical byte count" in output
    assert "docker compose is required" not in output


@pytest.mark.skipif(BASH is None, reason="Bash is required for legacy preflight contract")
def test_legacy_production_preflight_rejects_public_http_before_reading_env(tmp_path):
    env_file = tmp_path / ".env.production"
    env_file.write_text("SHOULD_NOT_BE_READ=1\n", encoding="utf-8")
    nginx_config = tmp_path / "unsafe-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://203.0.113.10:18080/api/; } }\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            BASH,
            "scripts/production-preflight.sh",
            env_file.as_posix(),
            nginx_config.as_posix(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0, output
    assert "public plaintext HTTP upstream" in output
    assert "Required variable" not in output


@pytest.mark.skipif(BASH is None, reason="Bash is required for legacy preflight contract")
def test_legacy_preflight_rejects_undocumented_compose_control_variables(tmp_path):
    env_file = tmp_path / ".env.production"
    env_file.write_text("COMPOSE_PROJECT_NAME=unrelated-project\n", encoding="utf-8")
    env_path = _chmod_owner_only_or_skip(env_file)
    nginx_config = tmp_path / "secure-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    environment = dict(os.environ)
    environment["PYTHON_BIN"] = "/usr/bin/true"

    completed = subprocess.run(
        [
            BASH,
            "scripts/production-preflight.sh",
            env_path,
            _bash_absolute_path(nginx_config),
        ],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0, output
    assert "Production env file contains undocumented key COMPOSE_PROJECT_NAME" in output
    assert "Required variable RELEASE_ID" not in output


@pytest.mark.skipif(BASH is None, reason="Bash is required for legacy preflight contract")
def test_legacy_production_preflight_rejects_unverified_https_before_reading_env(
    tmp_path,
):
    env_file = tmp_path / ".env.production"
    env_file.write_text("SHOULD_NOT_BE_READ=1\n", encoding="utf-8")
    nginx_config = tmp_path / "unverified-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass https://origin.example.com/api/; } }\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            BASH,
            "scripts/production-preflight.sh",
            env_file.as_posix(),
            nginx_config.as_posix(),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )

    output = completed.stdout + completed.stderr
    assert completed.returncode != 0, output
    assert "proxy_ssl_verify on" in output
    assert "proxy_ssl_server_name on" in output
    assert "Required variable" not in output
