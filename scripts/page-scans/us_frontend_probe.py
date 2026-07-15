import json
import re
import shlex
import statistics
import sys
from datetime import UTC, datetime
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.prod_deploy import REPO_ROOT as DEPLOY_REPO_ROOT, RemoteHost, load_config


OUTPUT_DIR = DEPLOY_REPO_ROOT / "output" / "playwright"
CONFIG_PATH = DEPLOY_REPO_ROOT / ".deploy.prod.json"
STATIC_PREFIXES = [
    "index-",
    "runtime-dom.esm-bundler-",
    "DashboardPage-",
    "DataPage-",
    "AccountsPage-",
    "OrdersPage-",
    "MessagesPage-",
    "ProfileCenterPage-",
]
BASE_API_PATHS = [
    "/api/navigation/home?limit=5",
    "/api/dashboard/summary",
    "/api/dashboard/sales-trend",
    "/api/xianyu/accounts/lite?current=1&size=100",
    "/api/xianyu/accounts?current=1&size=100",
    "/api/orders?current=1&size=20",
    "/api/goods/stats",
    "/api/ai-billing/balance",
    "/api/business-settings/ai-customer-service",
    "/api/profile/overview",
]
ACCOUNT_SCOPED_API_PATHS = [
    "/api/msg/online/conversations?xianyuAccountId={account_id}&pageSize=50",
    "/api/auto-reply-scope/products?accountId={account_id}",
    "/api/auto-reply-scope/status?accountId={account_id}",
]
CURL_TIMEOUT_SECONDS = 30
CURL_METRICS_FORMAT = (
    '{"http_code":"%{http_code}","time_namelookup":%{time_namelookup},'
    '"time_connect":%{time_connect},"time_starttransfer":%{time_starttransfer},'
    '"time_total":%{time_total}}'
)


def find_first_asset(dist_assets: Path, prefix: str) -> str | None:
    matches = sorted(path.name for path in dist_assets.glob(f"{prefix}*"))
    return matches[0] if matches else None


def discover_static_paths() -> list[str]:
    index_html = (REPO_ROOT / "apps" / "user-web" / "dist" / "index.html").read_text(encoding="utf-8")
    index_match = re.search(r'src="(/assets/index-[^"]+\.js)"', index_html)
    paths: list[str] = ["/"]
    if index_match:
        paths.append(index_match.group(1))

    dist_assets = DEPLOY_REPO_ROOT / "apps" / "user-web" / "dist" / "assets"
    for prefix in STATIC_PREFIXES[1:]:
        asset_name = find_first_asset(dist_assets, prefix)
        if asset_name:
            paths.append(f"/assets/{asset_name}")

    # Keep order stable while removing duplicates.
    seen: set[str] = set()
    deduped: list[str] = []
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def quote_single(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_curl_command(url: str, auth_header_path: str | None = None) -> str:
    header_args = ""
    if auth_header_path:
        header_args = f'-H "$(cat {shlex.quote(auth_header_path)})"'
    return "\n".join([
        "set -uo pipefail",
        "status=0",
        "metrics=$(",
        f"  curl -sS --max-time {CURL_TIMEOUT_SECONDS} -o /dev/null {header_args} "
        f"-w {quote_single(CURL_METRICS_FORMAT)} {shlex.quote(url)} 2>/dev/null",
        ") || status=$?",
        'printf "%s\\n__CURL_EXIT__=%s\\n" "$metrics" "$status"',
    ])


def parse_probe_output(output: str) -> dict:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    exit_line = next((line for line in reversed(lines) if line.startswith("__CURL_EXIT__=")), "__CURL_EXIT__=0")
    metrics_line = next((line for line in reversed(lines) if line.startswith("{") and line.endswith("}")), None)

    curl_exit = int(exit_line.split("=", 1)[1])
    payload = json.loads(metrics_line) if metrics_line else {
        "http_code": "000",
        "time_namelookup": 0,
        "time_connect": 0,
        "time_starttransfer": 0,
        "time_total": 0,
    }
    payload["curl_exit"] = curl_exit
    payload["timed_out"] = curl_exit == 28
    payload["ok"] = curl_exit == 0
    if payload["timed_out"] and not payload.get("time_total"):
        payload["time_total"] = CURL_TIMEOUT_SECONDS
        payload["time_starttransfer"] = CURL_TIMEOUT_SECONDS
    return payload


def run_probe(remote: RemoteHost, url: str, samples: int, auth_header_path: str | None = None) -> dict:
    measurements = []
    for _ in range(samples):
        command = "bash -lc " + shlex.quote(build_curl_command(url, auth_header_path=auth_header_path))
        output, _, _ = remote.run(command, timeout=CURL_TIMEOUT_SECONDS + 30)
        payload = parse_probe_output(output)
        payload["time_total_ms"] = round(float(payload["time_total"]) * 1000)
        payload["time_starttransfer_ms"] = round(float(payload["time_starttransfer"]) * 1000)
        measurements.append(payload)

    totals = [item["time_total_ms"] for item in measurements]
    ttfbs = [item["time_starttransfer_ms"] for item in measurements]
    return {
        "url": url,
        "samples": measurements,
        "median_total_ms": round(statistics.median(totals)),
        "max_total_ms": max(totals),
        "median_ttfb_ms": round(statistics.median(ttfbs)),
        "max_ttfb_ms": max(ttfbs),
        "status_codes": sorted({item["http_code"] for item in measurements}),
        "success_count": sum(1 for item in measurements if item["ok"]),
        "timeout_count": sum(1 for item in measurements if item["timed_out"]),
        "error_count": sum(1 for item in measurements if not item["ok"]),
    }


def login_on_us_frontend(remote: RemoteHost, user_frontend_base: str, credentials: dict) -> str:
    login_url = user_frontend_base.rstrip("/") + "/api/login/login"
    body = json.dumps(credentials, ensure_ascii=False)
    command = (
        "bash -lc "
        + shlex.quote(
            "set -euo pipefail\n"
            "auth_header_file=$(mktemp /tmp/us-frontend-probe-auth.XXXXXX)\n"
            "curl -sS "
            + "-H 'Content-Type: application/json' "
            + f"-d {quote_single(body)} "
            + shlex.quote(login_url)
            + " | AUTH_HEADER_FILE=\"$auth_header_file\" python3 -c "
            + shlex.quote(
                "import json, os, sys\n"
                "payload = json.load(sys.stdin)\n"
                "token = payload.get('data', {}).get('token')\n"
                "if not token:\n"
                "    raise SystemExit('missing token')\n"
                "with open(os.environ['AUTH_HEADER_FILE'], 'w', encoding='utf-8') as handle:\n"
                "    handle.write('Authorization: Bearer ' + token)\n"
                "print(os.environ['AUTH_HEADER_FILE'])\n"
            )
        )
    )
    output, _, _ = remote.run(command, timeout=120)
    auth_header_path = output.strip().splitlines()[-1]
    if not auth_header_path:
        raise RuntimeError("US frontend login probe failed to persist authorization header")
    return auth_header_path


def discover_account_id(remote: RemoteHost, auth_header_path: str) -> str | None:
    url = "http://127.0.0.1:81/api/xianyu/accounts/lite?current=1&size=1"
    command = (
        "bash -lc "
        + shlex.quote(
            "set -euo pipefail\n"
            + "curl -sS "
            + f'--max-time {CURL_TIMEOUT_SECONDS} -H "$(cat {shlex.quote(auth_header_path)})" '
            + shlex.quote(url)
            + " | python3 -c "
            + shlex.quote(
                "import json, sys\n"
                "payload = json.load(sys.stdin)\n"
                "data = payload.get('data')\n"
                "records = []\n"
                "if isinstance(data, list):\n"
                "    records = data\n"
                "elif isinstance(data, dict):\n"
                "    for key in ('records', 'accounts', 'list', 'rows', 'items'):\n"
                "        value = data.get(key)\n"
                "        if isinstance(value, list):\n"
                "            records = value\n"
                "            break\n"
                "account_id = ''\n"
                "if records and isinstance(records[0], dict) and records[0].get('id') is not None:\n"
                "    account_id = str(records[0]['id'])\n"
                "print(account_id)\n"
            )
        )
    )
    output, _, _ = remote.run(command, timeout=CURL_TIMEOUT_SECONDS + 30, check=False)
    account_id = output.strip().splitlines()[-1] if output.strip() else ""
    return account_id or None


def cleanup_remote_auth(remote: RemoteHost, auth_header_path: str | None):
    if not auth_header_path:
        return
    command = "bash -lc " + shlex.quote(f"rm -f {shlex.quote(auth_header_path)}")
    remote.run(command, timeout=30, check=False)


def build_api_paths(account_id: str | None) -> list[str]:
    paths = list(BASE_API_PATHS)
    if account_id:
        paths.extend(path.format(account_id=account_id) for path in ACCOUNT_SCOPED_API_PATHS)
    return paths


def main():
    config = load_config(CONFIG_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    static_paths = discover_static_paths()
    user_frontend_base = config["smoke"]["user_frontend_base"]
    china_backend_base = config["smoke"]["china_backend_base"]
    output_path = OUTPUT_DIR / f"us-frontend-probe-{datetime.now(UTC).strftime('%Y-%m-%dT%H-%M-%S-%fZ')}.json"

    with RemoteHost("us-frontend", config["us_frontend"], False) as remote:
        auth_header_path = login_on_us_frontend(remote, "http://127.0.0.1:81", config["smoke"]["user_credentials"])
        try:
            selected_account_id = discover_account_id(remote, auth_header_path)
            api_paths = build_api_paths(selected_account_id)

            static_results = []
            for path in static_paths:
                static_results.append(
                    run_probe(remote, f"http://127.0.0.1:81{path}", samples=3)
                )

            frontend_api_results = []
            backend_api_results = []
            for path in api_paths:
                frontend_api_results.append(
                    run_probe(remote, f"http://127.0.0.1:81{path}", samples=3, auth_header_path=auth_header_path)
                )
                backend_api_results.append(
                    run_probe(remote, f"{china_backend_base.rstrip('/')}{path}", samples=3, auth_header_path=auth_header_path)
                )
        finally:
            cleanup_remote_auth(remote, auth_header_path)

    report = {
        "scannedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "selectedAccountId": selected_account_id,
        "static": static_results,
        "frontendApis": frontend_api_results,
        "backendApis": backend_api_results,
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "reportPath": str(output_path),
        "staticSlowestMedianMs": max(item["median_total_ms"] for item in static_results) if static_results else 0,
        "frontendApiSlowestMedianMs": max(item["median_total_ms"] for item in frontend_api_results) if frontend_api_results else 0,
        "frontendApiTimeoutCount": sum(item["timeout_count"] for item in frontend_api_results),
        "backendApiSlowestMedianMs": max(item["median_total_ms"] for item in backend_api_results) if backend_api_results else 0,
        "backendApiTimeoutCount": sum(item["timeout_count"] for item in backend_api_results),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
