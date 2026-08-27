import re
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_runtime_images_use_non_root_users_and_specific_base_lines():
    core = read("apps/core-api/Dockerfile")
    automation = read("apps/automation-service/Dockerfile")
    crawler = read("apps/crawler-service/Dockerfile")
    admin = read("apps/admin-web/Dockerfile")
    user = read("apps/user-web/Dockerfile")

    assert "FROM maven:3.9.16-eclipse-temurin-17 AS build" in core
    assert "USER 10001:10001" in core
    assert "USER 10001:10001" in automation
    assert "USER pwuser" in crawler
    assert crawler.count("mcr.microsoft.com/playwright:v1.61.1-noble") == 2
    assert "FROM node:24.18.0-alpine AS build" in admin
    assert "FROM node:24.18.0-alpine AS build" in user
    assert "COPY . ." not in crawler
    assert "npm prune --omit=dev" in crawler
    assert "COPY --from=build" in crawler
    assert "nginxinc/nginx-unprivileged:1.30.3-alpine" in admin
    assert "nginxinc/nginx-unprivileged:1.30.3-alpine" in user
    assert "EXPOSE 8080" in admin
    assert "EXPOSE 8080" in user


def test_docker_build_contexts_exclude_credentials_and_runtime_artifacts():
    for app in ("core-api", "automation-service", "crawler-service", "admin-web", "user-web"):
        dockerignore = read(f"apps/{app}/.dockerignore")
        assert ".env.*" in dockerignore
        assert "*cookie*.txt" in dockerignore
        assert "*token*.txt" in dockerignore
        assert "*.har" in dockerignore
        assert "*.log" in dockerignore
        assert "*.bak" in dockerignore
        assert "*.codex-bak" in dockerignore
        assert "*.orig" in dockerignore
        assert "*.rej" in dockerignore
    crawler_ignore = read("apps/crawler-service/.dockerignore")
    assert "scripts/" in crawler_ignore
    assert "*_dump.json" in crawler_ignore
    assert "*_response.json" in crawler_ignore


def test_compose_uses_least_privilege_database_account_and_container_guards():
    compose = read("docker-compose.yml")

    assert "SPRING_DATASOURCE_USERNAME: ${MYSQL_APP_USER:-xianyu_app}" in compose
    assert "MYSQL_USER: ${MYSQL_APP_USER:-xianyu_app}" in compose
    assert "MYSQL_PASSWORD: ${MYSQL_APP_PASSWORD:-dev-only-mysql-app-password-change-me}" in compose
    assert compose.count("no-new-privileges:true") >= 7
    assert compose.count("init: true") >= 7
    assert compose.count("read_only: true") >= 7
    assert compose.count("cap_drop:") >= 7
    # /home/pwuser tmpfs is sized 128m (raised from 64m alongside /tmp 4g:
    # Chrome needs writable HOME space for crashpad + profile spillover).
    assert compose.count("/home/pwuser:rw,noexec,nosuid,size=128m") == 2
    assert "internal: true" in compose
    assert "condition: service_healthy" in compose
    assert "http://127.0.0.1:3001/api/ready" in compose
    assert compose.count("COOKIE_CRYPTO_SECRET: ${COOKIE_CRYPTO_SECRET:?COOKIE_CRYPTO_SECRET must be set}") >= 4
    assert "DATABASE_URL: postgres://${CRAWLER_DB_USER" not in compose
    assert compose.count("CRAWLER_DB_PASSWORD: ${CRAWLER_DB_PASSWORD:-crawler_pass}") == 2
    assert "image: mysql:8.4.10" in compose
    assert "image: redis:7.4.9-alpine" in compose
    assert "image: postgres:16.14-alpine" in compose
    infrastructure = read("docker-compose.infrastructure.yml")
    for model in (compose, infrastructure):
        assert '--password="$${MYSQL_ROOT_PASSWORD}"' in model
        assert " -p$${MYSQL_ROOT_PASSWORD}" not in model
    assert "image: mysql:8.4.10" in infrastructure
    assert "image: redis:7.4.9-alpine" in infrastructure
    assert "image: postgres:16.14-alpine" in infrastructure


def test_every_upload_writer_uses_one_writable_volume_and_production_limits_are_explicit():
    compose = read("docker-compose.yml")
    production = read("docker-compose.prod.yml")
    core_dockerfile = read("apps/core-api/Dockerfile")

    assert compose.count("uploads_data:/app/uploads") == 3
    assert "uploads_data:" in compose
    assert "/app/apps/automation-service/uploads" not in compose
    assert "XIANYU_UPLOAD_ROOT_DIR: /app/uploads" in compose
    assert "mkdir -p /app/uploads" in core_dockerfile
    assert "http://127.0.0.1:12401/ready" in compose
    assert "http://127.0.0.1:18080/api/ops/readiness" in production
    assert production.count('UPLOAD_GOVERNANCE_ENABLED: "true"') == 3
    assert len(re.findall(r"^\s+UPLOAD_MAX_CONCURRENT_GLOBAL:", production, re.MULTILINE)) == 3
    assert "MEDIA_COOKIE_SECURE: \"true\"" in production


def test_production_services_have_fail_closed_resource_and_shutdown_ceiling_contracts():
    application = yaml.safe_load(read("docker-compose.prod.yml"))
    monitoring = yaml.safe_load(read("docker-compose.monitoring.yml"))
    env_example = read(".env.production.example")
    preflight = read("scripts/production-preflight.sh")

    expected_application = {
        "mysql",
        "redis",
        "crawler-postgres",
        "backend",
        "automation",
        "automation-worker",
        "crawler-service",
        "crawler-worker",
        "user-web",
        "admin-web",
    }
    expected_monitoring = {
        "blackbox-exporter",
        "alertmanager",
        "prometheus",
        "grafana",
    }

    assert set(application["services"]) == expected_application
    assert set(monitoring["services"]) == expected_monitoring
    for service_name, service in {
        **application["services"],
        **monitoring["services"],
    }.items():
        assert str(service.get("mem_limit", "")).startswith("${"), service_name
        assert str(service.get("cpus", "")).startswith("${"), service_name
        assert str(service.get("pids_limit", "")).startswith("${"), service_name
        assert service.get("stop_grace_period"), service_name

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
        for suffix in ("MEMORY_LIMIT_BYTES", "CPUS", "PIDS_LIMIT"):
            key = f"{prefix}_{suffix}"
            assert f"{key}=" in env_example
            assert key in preflight
    assert "Production resource ceilings passed" in preflight


def test_every_fail_closed_compose_input_is_documented_and_preflighted():
    compose = "\n".join(
        read(relative)
        for relative in (
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "docker-compose.monitoring.yml",
        )
    )
    env_example = read(".env.production.example")
    preflight = read("scripts/production-preflight.sh")
    required_variables = set(re.findall(r"\$\{([A-Z][A-Z0-9_]+):\?", compose))

    assert required_variables
    for variable in required_variables:
        assert re.search(rf"(?m)^{variable}=", env_example), variable
        assert re.search(rf"(?m)^  {variable}$", preflight), variable


def test_host_published_service_data_and_monitoring_ports_are_loopback_only():
    compose = read("docker-compose.yml")
    infrastructure = read("docker-compose.infrastructure.yml")
    monitoring = read("docker-compose.monitoring.yml")
    nginx = read("deploy/nginx/us-nginx-full.conf")

    # Backend 18080 stays reachable on all interfaces: the cross-region edge
    # (deploy/nginx/us-nginx-full.conf) proxies to this host over the WireGuard
    # private path 10.0.0.1:18080, and iptables restricts the port to
    # 10.0.0.0/24 + the edge server IP only. The web frontends, databases and
    # monitoring ports must remain loopback-only.
    assert "${BACKEND_PORT:-18080}:18080" in compose
    for binding in (
        "127.0.0.1:${ADMIN_WEB_PORT:-3006}:8080",
        "127.0.0.1:${USER_WEB_PORT:-5174}:8080",
    ):
        assert binding in compose
    for binding in (
        "127.0.0.1:${MYSQL_PORT:-3306}:3306",
        "127.0.0.1:${REDIS_PORT:-6379}:6379",
        "127.0.0.1:${CRAWLER_DB_PORT:-5432}:5432",
    ):
        assert binding in infrastructure
    assert "127.0.0.1:${PROMETHEUS_PORT:-9090}:9090" in monitoring
    assert "127.0.0.1:${GRAFANA_PORT:-3000}:3000" in monitoring
    assert "listen 127.0.0.1:81;" in nginx
    assert "listen 127.0.0.1:82;" in nginx
    assert "listen 81;" not in nginx
    assert "listen 82;" not in nginx
    assert "listen 8080;" in read("apps/admin-web/nginx.conf")
    assert "listen 8080;" in read("apps/user-web/nginx.conf")
    for frontend in ("admin-web", "user-web"):
        frontend_nginx = read(f"apps/{frontend}/nginx.conf")
        assert "location ^~ /assets/" in frontend_nginx
        assert "expires 1y;" in frontend_nginx
        assert "expires 1h;" in frontend_nginx
    assert compose.count("http://127.0.0.1:8080/") == 2


def test_monitoring_scrape_is_authenticated_and_services_are_hardened():
    compose = read("docker-compose.monitoring.yml")
    prometheus = read("monitoring/prometheus/prometheus.yml")
    alerts = read("monitoring/prometheus/alert.rules.yml")
    alertmanager = read("monitoring/alertmanager/alertmanager.yml")
    dashboard = read("monitoring/grafana/dashboards/xianyu-overview.json")
    dashboard_provisioning = read("monitoring/grafana/provisioning/dashboards/dashboards.yml")
    env_example = read(".env.production.example")

    assert "credentials_file: /run/secrets/ops_metrics_token" in prometheus
    assert "authorization:" in prometheus
    assert "OPS_METRICS_TOKEN_FILE" in compose
    assert "OPS_METRICS_TOKEN_FILE" in env_example
    assert "MONITORING_SECRET_GID" in env_example
    assert compose.count("65534:${MONITORING_SECRET_GID:") == 2
    assert 'user: "65534:65534"' in compose
    assert "alertmanagers:" in prometheus
    assert "alertmanager:9093" in prometheus
    assert "job_name: alertmanager" in prometheus
    assert "job_name: service-readiness" in prometheus
    assert "replacement: blackbox-exporter:9115" in prometheus
    assert "core-api-readiness" not in prometheus
    assert "quay.io/prometheus/blackbox-exporter:v0.28.0" in compose
    assert "--profile monitoring" in compose
    blackbox = read("monitoring/blackbox/blackbox.yml")
    assert "valid_status_codes: [200]" in blackbox
    assert "follow_redirects: false" in blackbox
    assert "public_https:" in blackbox
    assert "fail_if_not_ssl: true" in blackbox
    assert "insecure_skip_verify: false" in blackbox
    for service in ("core-api", "automation-service", "crawler-service"):
        assert f"service: {service}" in prometheus
        assert f'service="{service}"' in alerts
    assert "CriticalServiceNotReady" in alerts
    assert "CriticalServiceProbeMissing" in alerts
    assert "BlackboxExporterDown" in alerts
    assert "job_name: public-availability" in prometheus
    # The public-availability probe ships with placeholder domains
    # (example.com) so the open-source tree stays deployment-neutral;
    # operators replace them with their own domains.
    for target in (
        "https://www.example.com/",
        "https://www.example.com/api/health",
        "https://admin.example.com/",
    ):
        assert target in prometheus
    assert "PublicEndpointDown" in alerts
    assert "PublicEndpointProbeMissing" in alerts
    assert "PublicTlsCertificateExpiresSoon" in alerts
    assert 'probe_ssl_earliest_cert_expiry{job="public-availability"}' in alerts
    assert "RedisDown" in alerts
    assert "xianyu_core_redis_up" in alerts
    assert "xianyu_core_redis_up" in dashboard
    assert 'probe_success{job=\\"service-readiness\\"}' in dashboard
    assert 'probe_success{job=\\"public-availability\\"}' in dashboard
    assert 'probe_ssl_earliest_cert_expiry{job=\\"public-availability\\"}' in dashboard
    assert "disableDeletion: true" in dashboard_provisioning
    assert "editable: false" in dashboard_provisioning
    assert "prom/alertmanager:v0.32.1" in compose
    assert "ALERTMANAGER_WEBHOOK_URL_FILE" in compose
    assert "ALERTMANAGER_WEBHOOK_URL_FILE" in env_example
    assert "url_file: /run/secrets/alertmanager_webhook_url" in alertmanager
    assert "send_resolved: true" in alertmanager
    assert 'alertname="XianyuWatchdog"' in alertmanager
    assert "null" not in alertmanager.lower()
    assert "prom/prometheus:v3.5.3" in compose
    assert "grafana/grafana:12.4.5" in compose
    assert "http://127.0.0.1:9090/-/ready" in compose
    assert "http://127.0.0.1:3000/api/health" in compose
    assert "GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password" in compose
    assert "GF_SECURITY_ADMIN_PASSWORD:" not in compose
    assert 'GF_AUTH_ANONYMOUS_ENABLED: "false"' in compose
    assert 'GF_SECURITY_COOKIE_SECURE: "true"' in compose
    assert "GF_SECURITY_COOKIE_SAMESITE: strict" in compose
    assert 'GF_ANALYTICS_REPORTING_ENABLED: "false"' in compose
    assert "GRAFANA_ADMIN_PASSWORD_FILE" in compose
    assert "GRAFANA_ADMIN_PASSWORD_FILE" in env_example
    assert "grafana_admin_password:" in compose
    assert "group_add:" in compose
    assert "--storage.tsdb.retention.size=${PROMETHEUS_RETENTION_SIZE:" in compose
    assert compose.count("driver: json-file") == 4
    assert compose.count('max-size: "20m"') == 4
    assert compose.count("condition: service_healthy") >= 4
    assert "--web.enable-lifecycle" not in compose
    assert compose.count("no-new-privileges:true") == 4
    assert compose.count("cap_drop:") == 4
    assert compose.count("read_only: true") == 4
    assert compose.count("- app") == 4


def test_production_overlay_activates_every_services_fail_closed_profile():
    overlay = read("docker-compose.prod.yml")

    assert "SPRING_PROFILES_ACTIVE: prod" in overlay
    assert "AI_PROVIDER_ALLOWED_HOSTS: ${AI_PROVIDER_ALLOWED_HOSTS:?" in overlay
    assert overlay.count("APP_ENV: production") == 2
    assert overlay.count("NODE_ENV: production") == 2


def test_frontend_nginx_configs_emit_browser_security_headers():
    required = (
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
    )
    for relative in (
        "apps/admin-web/nginx.conf",
        "apps/user-web/nginx.conf",
        "deploy/nginx/us-nginx-full.conf",
    ):
        config = read(relative)
        for header in required:
            assert header in config


def test_uploaded_assets_always_use_the_backend_and_fail_closed_cache_policy():
    # The container frontends proxy uploads through their keepalive upstream
    # pool (backend_pool -> backend:18080); xianyupilot-ssl.conf proxies to
    # its origin pool. The US edge serves uploads from its local mirror
    # behind a media-session cookie check and relays misses to the verified
    # HTTPS origin instead of the plaintext tunnel.
    configs = {
        "apps/admin-web/nginx.conf": (1, "http://backend_pool/uploads/"),
        "apps/user-web/nginx.conf": (1, "http://backend_pool/uploads/"),
        "deploy/nginx/xianyupilot-ssl.conf": (2, "http://backend_pool/uploads/"),
    }

    for relative, (expected_count, upstream) in configs.items():
        config = read(relative)
        blocks = re.findall(r"location \^~ /uploads/ \{([^{}]*)\}", config, re.DOTALL)

        assert len(blocks) == expected_count, relative
        assert "location /uploads/ {" not in config, relative
        assert "proxy_cookie_domain" not in config, relative
        assert "proxy_cookie_path" not in config, relative
        for block in blocks:
            assert f"proxy_pass {upstream};" in block, relative
            if relative != "deploy/nginx/xianyupilot-ssl.conf":
                assert "proxy_set_header X-Request-ID $request_id;" in block, relative
            assert 'proxy_set_header Cookie "";' not in block, relative
            assert 'proxy_hide_header Cache-Control;' in block, relative
            assert 'proxy_hide_header Expires;' in block, relative
            assert 'proxy_cache off;' in block, relative
            assert 'add_header Cache-Control "private, no-store, max-age=0" always;' in block, relative
            assert 'add_header Pragma "no-cache" always;' in block, relative
            assert 'add_header Expires "0" always;' in block, relative
            assert 'add_header X-Content-Type-Options "nosniff" always;' in block, relative
            assert 'add_header X-Frame-Options "DENY" always;' in block, relative
            assert 'add_header Content-Security-Policy "default-src \'none\'; frame-ancestors \'none\'; sandbox" always;' in block, relative
            assert 'add_header Referrer-Policy "no-referrer" always;' in block, relative
            assert 'add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;' in block, relative
            assert 'add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;' in block, relative

    # US edge: every vhost serves /uploads/ from the local mirror behind a
    # media-session cookie check (user and admin variants) and relays misses
    # to the verified HTTPS origin with SNI + request-id propagation.
    edge = read("deploy/nginx/us-nginx-full.conf")
    edge_uploads = re.findall(
        r"location \^~ /uploads/ \{.*?\n    \}", edge, re.DOTALL
    )
    edge_relays = re.findall(
        r"location @uploads_relay \{.*?\n    \}", edge, re.DOTALL
    )
    assert len(edge_uploads) == 4
    assert len(edge_relays) == 4
    assert "location /uploads/ {" not in edge
    assert "proxy_cookie_domain" not in edge
    assert "proxy_cookie_path" not in edge
    assert "http://127.0.0.1:18081/uploads/" not in edge
    for block in edge_uploads:
        assert "alias /var/www/uploads-data/;" in block
        assert "$cookie_xianyu_media_" in block
        assert "return 403;" in block
        assert "error_page 404 = @uploads_relay;" in block
    for block in edge_relays:
        assert "proxy_pass https://backend.example.com;" in block
        assert "proxy_ssl_server_name on;" in block
        assert "proxy_ssl_name backend.example.com;" in block
        assert "proxy_set_header X-Request-ID $request_id;" in block


def test_automation_image_installs_hash_locked_audited_dependencies():
    dockerfile = read("apps/automation-service/Dockerfile")
    direct = read("apps/automation-service/requirements.txt")
    locked = read("apps/automation-service/requirements.lock")

    assert "COPY requirements.lock ./" in dockerfile
    assert "pip install --no-cache-dir --require-hashes -r requirements.lock" in dockerfile
    assert "--generate-hashes" in locked.splitlines()[1]
    assert "--python-platform x86_64-manylinux_2_28" in locked.splitlines()[1]
    assert locked.count("--hash=sha256:") >= 50

    # Keep the direct pins that close the vulnerabilities found during the
    # production dependency audit. The transitive Starlette pin proves that
    # the FastAPI upgrade resolved to the remediated compatibility line.
    for dependency in (
        "fastapi==0.139.0",
        "aiomysql==0.3.0",
        "pyjwt==2.13.0",
        "python-multipart==0.0.31",
        "requests==2.33.0",
        "Pillow==12.2.0",
        "msgpack==1.2.1",
        "cryptography==48.0.1",
    ):
        assert dependency.lower() in direct.lower()
    assert "starlette==1.3.1" in locked
