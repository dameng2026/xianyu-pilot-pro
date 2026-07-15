from pathlib import Path
import json
import re
from urllib.parse import urlsplit

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github/workflows/ci.yml"
RELEASE_REQUIREMENTS = REPO_ROOT / "scripts/requirements-ci.txt"
RELEASE_REQUIREMENTS_LOCK = REPO_ROOT / "scripts/requirements-ci.lock"
TRIVY_ACTION = (
    "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25"
)
UPLOAD_ARTIFACT_ACTION = (
    "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
)


def test_ci_covers_every_deployable_and_release_contracts():
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw)
    jobs = workflow["jobs"]

    assert set(jobs) == {
        "core-api",
        "automation-service",
        "crawler-service",
        "user-web",
        "admin-web",
        "release-contracts",
        "container-supply-chain",
        "release-provenance-gate",
        "secret-history-scan",
        "monitoring-config",
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert "continue-on-error" not in raw
    assert "|| true" not in raw


def test_ci_uses_locked_installs_and_full_quality_gates():
    raw = WORKFLOW.read_text(encoding="utf-8")

    assert "--require-hashes -r requirements-dev.lock" in raw
    assert "python -m pip install pip-audit" not in raw
    assert "pip-audit -r requirements.lock --no-deps --disable-pip --strict" in raw
    assert raw.count("npm ci --no-audit --no-fund --strict-allow-scripts") == 3
    assert raw.count("npm audit --audit-level=low") == 3
    assert raw.count(
        'test "$(node --version)" = "v24.18.0" '
        '&& test "$(npm --version)" = "11.16.0"'
    ) == 3
    assert "npm audit --omit=dev" not in raw
    assert raw.count('node-version: "24.18.0"') == 3
    assert "./mvnw --batch-mode --no-transfer-progress verify" in raw
    assert "-Psupply-chain-audit verify" in raw
    assert "NVD_API_KEY: ${{ secrets.NVD_API_KEY }}" in raw
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in raw
    assert "target/supply-chain/sbom.json" in raw
    assert "npm run check" in raw
    assert raw.count("npm run check") == 2
    assert "python -m pytest -q scripts/tests" in raw


def test_npm_install_scripts_are_explicitly_reviewed_and_fail_closed():
    for relative_path in (
        "apps/admin-web/package.json",
        "apps/user-web/package.json",
        "apps/crawler-service/package.json",
    ):
        package = json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
        policy = package.get("allowScripts")
        assert isinstance(policy, dict) and policy, f"{relative_path} must declare allowScripts"
        assert not any(str(name).startswith("file:") for name in policy)
        assert all(isinstance(allowed, bool) for allowed in policy.values())
        assert all(
            allowed is False or name == "esbuild@0.28.1"
            for name, allowed in policy.items()
        )

        lock = json.loads(
            (REPO_ROOT / relative_path.replace("package.json", "package-lock.json"))
            .read_text(encoding="utf-8")
        )
        for installed_path, metadata in lock.get("packages", {}).items():
            if not isinstance(metadata, dict) or not metadata.get("hasInstallScript"):
                continue
            package_name = installed_path.rsplit("node_modules/", 1)[-1]
            version = metadata.get("version")
            assert package_name in policy or f"{package_name}@{version}" in policy, (
                f"{relative_path} has an unreviewed install script: "
                f"{package_name}@{version}"
            )

    crawler_dockerfile = (
        REPO_ROOT / "apps/crawler-service/Dockerfile"
    ).read_text(encoding="utf-8")
    assert crawler_dockerfile.count(
        'test "$(node --version)" = "v24.18.0"'
    ) == 2
    assert crawler_dockerfile.count(
        'test "$(npm --version)" = "11.16.0"'
    ) == 2
    assert "npm ci --no-audit --no-fund --strict-allow-scripts" in crawler_dockerfile
    assert "npm prune --omit=dev --no-audit --strict-allow-scripts" in crawler_dockerfile
    for app in ("admin-web", "user-web"):
        dockerfile = (REPO_ROOT / "apps" / app / "Dockerfile").read_text(
            encoding="utf-8"
        )
        assert 'test "$(node --version)" = "v24.18.0"' in dockerfile
        assert 'test "$(npm --version)" = "11.16.0"' in dockerfile
        assert "npm ci --no-audit --no-fund --strict-allow-scripts" in dockerfile
        assert "--ignore-scripts" not in dockerfile


def test_node_release_artifacts_have_truthful_private_package_identity():
    expected = {
        "apps/admin-web": "xianyu-assistant-admin-web",
        "apps/user-web": "xianyu-assistant-user-web",
        "apps/crawler-service": "xianyu-crawler-service",
    }
    for relative_root, package_name in expected.items():
        package = json.loads(
            (REPO_ROOT / relative_root / "package.json").read_text(encoding="utf-8")
        )
        lock = json.loads(
            (REPO_ROOT / relative_root / "package-lock.json").read_text(encoding="utf-8")
        )
        assert package["name"] == package_name
        assert package["version"] == "1.0.0"
        assert package["private"] is True
        assert lock["name"] == package["name"]
        assert lock["version"] == package["version"]
        assert lock["packages"][""]["name"] == package["name"]
        assert lock["packages"][""]["version"] == package["version"]


def test_dependency_audit_evidence_is_retained_even_when_the_gate_rejects():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]

    java_upload = jobs["core-api"]["steps"][-1]
    assert java_upload["uses"] == UPLOAD_ARTIFACT_ACTION
    assert java_upload["if"] == "${{ always() }}"

    expected_reports = {
        "automation-service": "automation-service.pip-audit.json",
        "crawler-service": "crawler-service.npm-audit.json",
        "user-web": "user-web.npm-audit.json",
        "admin-web": "admin-web.npm-audit.json",
    }
    for job_name, report_name in expected_reports.items():
        steps = jobs[job_name]["steps"]
        sbom_index = next(
            index for index, step in enumerate(steps)
            if step.get("uses") == TRIVY_ACTION
        )
        audit_index = next(
            index for index, step in enumerate(steps)
            if report_name in str(step.get("run", ""))
        )
        upload_index = next(
            index for index, step in enumerate(steps)
            if step.get("uses") == UPLOAD_ARTIFACT_ACTION
        )
        upload = steps[upload_index]

        assert sbom_index < audit_index < upload_index
        assert upload["if"] == "${{ always() }}"
        assert report_name in upload["with"]["path"]


def test_every_non_java_application_emits_a_cyclonedx_sbom_artifact():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    expected_scan_refs = {
        "automation-service": "apps/automation-service",
        "crawler-service": "apps/crawler-service",
        "user-web": "apps/user-web",
        "admin-web": "apps/admin-web",
    }

    for job_name, scan_ref in expected_scan_refs.items():
        steps = jobs[job_name]["steps"]
        sbom_steps = [step for step in steps if step.get("uses") == TRIVY_ACTION]
        assert len(sbom_steps) == 1
        assert {
            "scan-type": "fs",
            "scan-ref": scan_ref,
            "format": "cyclonedx",
            "exit-code": "0",
            "version": "v0.70.0",
        }.items() <= sbom_steps[0]["with"].items()
        upload_steps = [
            step for step in steps if step.get("uses") == UPLOAD_ARTIFACT_ACTION
        ]
        assert len(upload_steps) == 1
        assert upload_steps[0]["with"]["if-no-files-found"] == "error"
        assert upload_steps[0]["with"]["retention-days"] == 30
        assert ".cdx.json" in upload_steps[0]["with"]["path"]


def test_ci_builds_and_scans_every_production_container_subject():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["container-supply-chain"]
    include = job["strategy"]["matrix"]["include"]

    expected_build_contexts = {
        "./apps/core-api",
        "./apps/automation-service",
        "./apps/crawler-service",
        "./apps/admin-web",
        "./apps/user-web",
    }
    expected_external_images = {
        "mysql:8.4.10",
        "redis:7.4.9-alpine",
        "postgres:16.14-alpine",
        "quay.io/prometheus/blackbox-exporter:v0.28.0",
        "prom/alertmanager:v0.32.1",
        "prom/prometheus:v3.5.3",
        "grafana/grafana:12.4.5",
    }
    assert {entry["context"] for entry in include if entry["kind"] == "build"} == (
        expected_build_contexts
    )
    assert {entry["image"] for entry in include if entry["kind"] == "pull"} == (
        expected_external_images
    )
    application_compose = yaml.safe_load(
        (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    monitoring_compose = yaml.safe_load(
        (REPO_ROOT / "docker-compose.monitoring.yml").read_text(encoding="utf-8")
    )
    compose_build_contexts = {
        service["build"]
        for service in application_compose["services"].values()
        if isinstance(service.get("build"), str)
    }
    compose_external_images = {
        service["image"]
        for compose in (application_compose, monitoring_compose)
        for service in compose["services"].values()
        if service.get("image")
    }
    assert compose_build_contexts == expected_build_contexts
    assert compose_external_images == expected_external_images
    assert job["permissions"] == {"contents": "read"}
    assert job["strategy"]["fail-fast"] is False
    assert set(job["needs"]) == {
        "core-api",
        "automation-service",
        "crawler-service",
        "user-web",
        "admin-web",
        "release-contracts",
        "secret-history-scan",
        "monitoring-config",
    }

    steps = job["steps"]
    scans = [step for step in steps if step.get("uses") == TRIVY_ACTION]
    assert len(scans) == 2
    sbom, vulnerabilities = scans
    assert {
        "scan-type": "image",
        "image-ref": "${{ env.IMAGE_REF }}",
        "format": "cyclonedx",
        "exit-code": "0",
        "version": "v0.70.0",
    }.items() <= sbom["with"].items()
    assert {
        "scan-type": "image",
        "image-ref": "${{ env.IMAGE_REF }}",
        "format": "json",
        "severity": "HIGH,CRITICAL",
        "ignore-unfixed": "false",
        "exit-code": "1",
        "skip-setup-trivy": "true",
        "version": "v0.70.0",
    }.items() <= vulnerabilities["with"].items()
    uploads = [step for step in steps if step.get("uses") == UPLOAD_ARTIFACT_ACTION]
    assert len(uploads) == 1
    assert uploads[0]["if"] == "${{ always() }}"
    assert uploads[0]["with"]["if-no-files-found"] == "error"
    assert "*.cdx.json" in uploads[0]["with"]["path"]
    assert "*.vulnerabilities.json" in uploads[0]["with"]["path"]


def test_release_tags_are_fail_closed_until_registry_provenance_exists():
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw)
    job = workflow["jobs"]["release-provenance-gate"]

    assert job["permissions"] == {"contents": "read"}
    assert "startsWith(github.ref, 'refs/tags/')" in job["if"]
    assert job["steps"][-1]["run"].rstrip().endswith("exit 1")
    assert "registry-backed image signing and provenance are not configured" in raw
    assert "curl |" not in raw
    assert "wget |" not in raw


def test_monitoring_configuration_is_checked_with_the_production_tool_versions():
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = workflow["jobs"]["monitoring-config"]
    raw = "\n".join(str(step.get("run", "")) for step in job["steps"])

    assert job["permissions"] == {"contents": "read"}
    assert "prom/prometheus:v3.5.3" in raw
    assert "prom/alertmanager:v0.32.1" in raw
    assert "/bin/promtool" in raw
    assert "check config /etc/prometheus/prometheus.yml" in raw
    assert "/bin/amtool" in raw
    assert "check-config /etc/alertmanager/alertmanager.yml" in raw
    assert raw.count("--network none") == 2
    assert raw.count("--read-only") == 2
    assert raw.count("--cap-drop ALL") == 2
    assert raw.count("no-new-privileges") == 2


def test_secret_scan_is_redacted_fail_closed_and_covers_full_history():
    raw = WORKFLOW.read_text(encoding="utf-8")
    workflow = yaml.safe_load(raw)
    job = workflow["jobs"]["secret-history-scan"]
    checkout = job["steps"][0]
    install = job["steps"][1]
    scan = job["steps"][2]

    assert job["permissions"] == {"contents": "read"}
    assert checkout["uses"].startswith("actions/checkout@")
    assert checkout["with"] == {
        "fetch-depth": 0,
        "persist-credentials": False,
    }
    assert {
        "GITLEAKS_VERSION": "8.30.1",
        "GITLEAKS_ARCHIVE_SHA256": (
            "551f6fc83ea457d62a0d98237cbad105"
            "af8d557003051f41f3e7ca7b3f2470eb"
        ),
    }.items() <= install["env"].items()
    install_script = install["run"]
    assert "gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" in install_script
    assert "curl --fail --location --proto '=https' --tlsv1.2 --retry 3" in install_script
    assert "sha256sum --check --strict" in install_script
    assert "curl |" not in install_script
    assert "curl|" not in install_script
    scan_command = scan["run"]
    assert "gitleaks git" in scan_command
    assert "--redact=100" in scan_command
    assert "--log-opts=--all" in scan_command
    assert "--report-format=sarif" in scan_command
    assert "--exit-code=1" in scan_command
    upload = job["steps"][3]
    assert upload["if"] == "${{ always() }}"
    assert upload["uses"] == UPLOAD_ARTIFACT_ACTION
    assert upload["with"]["path"] == "results.sarif"
    assert upload["with"]["if-no-files-found"] == "error"
    assert "secret-history-scan" in workflow["jobs"]["container-supply-chain"]["needs"]
    assert ".gitleaksignore" not in raw
    assert "--no-git" not in raw


def test_release_contract_dependencies_are_fully_hash_locked():
    raw = WORKFLOW.read_text(encoding="utf-8")
    requirements = RELEASE_REQUIREMENTS.read_text(encoding="utf-8")
    lock = RELEASE_REQUIREMENTS_LOCK.read_text(encoding="utf-8")

    assert "cache-dependency-path: scripts/requirements-ci.lock" in raw
    assert (
        "python -m pip install --require-hashes -r scripts/requirements-ci.lock"
        in raw
    )
    assert "pip install pytest==" not in raw
    assert set(requirements.splitlines()) == {
        "paramiko==5.0.0",
        "pytest==8.3.4",
        "PyYAML==6.0.3",
    }

    lock_without_header = re.sub(r"\A(?:#.*\n)+\n?", "", lock)
    requirement_blocks = re.split(
        r"\n(?=[a-z0-9][a-z0-9._-]*==)", lock_without_header
    )
    requirement_blocks = [
        block
        for block in requirement_blocks
        if re.match(r"^[a-z0-9][a-z0-9._-]*==", block)
    ]
    assert requirement_blocks
    assert len(requirement_blocks) == len(
        re.findall(r"^[a-z0-9][a-z0-9._-]*==", lock, flags=re.MULTILINE)
    )
    assert {block.split("==", 1)[0] for block in requirement_blocks} >= {
        "paramiko",
        "pytest",
        "pyyaml",
    }
    for block in requirement_blocks:
        first_line = block.splitlines()[0]
        assert re.fullmatch(r"[a-z0-9][a-z0-9._-]*==[^\s\\]+ \\", first_line)
        assert re.search(r"--hash=sha256:[0-9a-f]{64}", block)


def test_ci_actions_are_pinned_to_immutable_commits():
    raw = WORKFLOW.read_text(encoding="utf-8")
    action_refs = re.findall(r"^\s*- uses:\s+([^\s#]+)", raw, flags=re.MULTILINE)

    assert action_refs
    assert all(re.fullmatch(r"[^@\s]+@[0-9a-f]{40}", ref) for ref in action_refs)
    assert "actions/checkout@v" not in raw
    assert "actions/setup-" not in re.sub(
        r"actions/setup-[^@\s]+@[0-9a-f]{40}", "", raw
    )


def test_node_toolchains_are_release_pinned():
    for app in ("crawler-service", "user-web", "admin-web"):
        package = json.loads((REPO_ROOT / "apps" / app / "package.json").read_text(encoding="utf-8"))
        assert package["packageManager"] == "npm@11.16.0"
        assert package["engines"] == {
            "node": ">=24.18.0 <27",
            "npm": ">=11.16.0 <12",
        }
    crawler = json.loads(
        (REPO_ROOT / "apps/crawler-service/package.json").read_text(encoding="utf-8")
    )
    assert crawler["dependencies"]["playwright"] == "1.61.1"


def test_node_lockfiles_use_the_public_canonical_registry():
    for app in ("crawler-service", "user-web", "admin-web"):
        lock_path = REPO_ROOT / "apps" / app / "package-lock.json"
        raw = lock_path.read_text(encoding="utf-8")
        lock = json.loads(raw)
        assert "applied-caas-gateway" not in raw
        assert "registry.npmmirror.com" not in raw
        resolved_urls = [
            metadata.get("resolved")
            for metadata in lock.get("packages", {}).values()
            if isinstance(metadata, dict) and metadata.get("resolved")
        ]
        assert resolved_urls
        assert all(urlsplit(url).hostname == "registry.npmjs.org" for url in resolved_urls)


def test_maven_toolchain_is_pinned_and_checksum_verified_on_every_platform():
    unix_wrapper = (REPO_ROOT / "apps/core-api/mvnw").read_text(encoding="utf-8")
    windows_wrapper = (REPO_ROOT / "apps/core-api/mvnw.cmd").read_text(encoding="utf-8")
    properties = (REPO_ROOT / "apps/core-api/.mvn/wrapper/maven-wrapper.properties").read_text(
        encoding="utf-8"
    )
    expected_tar_sha = (
        "831a8591fe20c8243b1dbe7d71e3244f31d1665b0804b2e825e38cbbe5ce0caf"
        "b8338851f90780735568773e0a6cd07bbec107cda0b896b008b861075358b6f6"
    )
    expected_zip_sha = (
        "ed41650d42485cfc243fad22158caf9cbb5dc408ce7a09ddb94dd42a019de929"
        "ca43065bfa450612cf12bf78b5cafa3884b96c090de326ff590448c933454af3"
    )

    for content in (unix_wrapper, windows_wrapper, properties):
        assert "3.9.16" in content
        assert "3.9.9" not in content
    assert expected_tar_sha in unix_wrapper
    assert expected_tar_sha in properties
    assert expected_zip_sha in windows_wrapper
    assert "command -v mvn" not in unix_wrapper
    assert "where mvn" not in windows_wrapper.lower()
