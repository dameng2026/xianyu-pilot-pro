import importlib.util
import shlex
import shutil
import subprocess
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "prod_deploy.py"
SPEC = importlib.util.spec_from_file_location("prod_deploy", MODULE_PATH)
prod_deploy = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(prod_deploy)

BASH = (
    "C:/Program Files/Git/bin/bash.exe"
    if Path("C:/Program Files/Git/bin/bash.exe").is_file()
    else shutil.which("bash")
)


class _FakeChannel:
    def __init__(self, stdout_chunks, stderr_chunks, exit_code=0):
        self.stdout_chunks = list(stdout_chunks)
        self.stderr_chunks = list(stderr_chunks)
        self.exit_code = exit_code
        self.closed = False

    def recv_ready(self):
        return bool(self.stdout_chunks)

    def recv(self, _size):
        return self.stdout_chunks.pop(0)

    def recv_stderr_ready(self):
        return bool(self.stderr_chunks)

    def recv_stderr(self, _size):
        return self.stderr_chunks.pop(0)

    def exit_status_ready(self):
        return not self.stdout_chunks and not self.stderr_chunks

    def recv_exit_status(self):
        if self.stdout_chunks or self.stderr_chunks:
            raise AssertionError("exit status read before draining remote output")
        return self.exit_code

    def close(self):
        self.closed = True


class _FakeStream:
    def __init__(self, channel):
        self.channel = channel


class _FakeStdin:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class _FakeClient:
    def __init__(self, channel, stdin, expected_timeout=None):
        self.channel = channel
        self.stdin = stdin
        self.expected_timeout = expected_timeout

    def exec_command(self, command, timeout):
        assert command == "echo test"
        if self.expected_timeout is not None:
            assert timeout == self.expected_timeout
        stream = _FakeStream(self.channel)
        return self.stdin, stream, stream


class _HostKeyCheckingClient:
    def __init__(self):
        self.loaded_system_keys = False
        self.policy = None
        self.connect_kwargs = None
        self.closed = False

    def load_system_host_keys(self):
        self.loaded_system_keys = True

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        self.connect_kwargs = kwargs

    def close(self):
        self.closed = True


class _RecordingRemote:
    def __init__(self):
        self.uploads = []
        self.commands = []
        self.client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def upload(self, local_path, remote_path):
        self.uploads.append((local_path, remote_path))

    def run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        return "", "", 0


class _FailingDeployRemote(_RecordingRemote):
    def run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if " up -d --build --force-recreate " in command and kwargs.get("check", True):
            raise prod_deploy.CommandError("simulated deploy failure")
        return "", "", 0


class _FailingRuntimeHealthRemote(_RecordingRemote):
    def run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if "runtime containers did not become healthy" in command and kwargs.get("check", True):
            raise prod_deploy.CommandError("simulated health failure")
        return "", "", 0


class _FailingDeployAndRollbackRemote(_FailingDeployRemote):
    def run(self, command, **kwargs):
        self.commands.append((command, kwargs))
        if not kwargs.get("check", True):
            return "", "rollback failed", 23
        if " up -d --build --force-recreate " in command:
            raise prod_deploy.CommandError("simulated deploy failure")
        return "", "", 0


@pytest.mark.parametrize(
    "name",
    ["module.py.bak", "module.py.codex-bak", "module.py.old", "module.py.orig", "module.py.rej", "module.py.swp"],
)
def test_release_bundle_excludes_editor_and_agent_backup_files(name):
    assert prod_deploy.is_excluded(Path("apps/automation-service/app") / name)


@pytest.mark.parametrize(
    "path",
    [
        Path("apps/automation-service/tests"),
        Path("apps/crawler-service/tests"),
        Path("apps/core-api/src/test"),
    ],
)
def test_release_bundle_excludes_test_source_trees(path):
    assert prod_deploy.is_excluded(path)


@pytest.mark.parametrize(
    "path",
    [
        Path("apps/automation-service/test_search.py"),
        Path("apps/automation-service/test_speed.py"),
        Path("apps/crawler-service/debug_browser.ts"),
        Path("apps/automation-service/provider_debug.py"),
        Path("apps/automation-service/module.spec.ts"),
        Path("apps/automation-service/module.test.js"),
    ],
)
def test_release_bundle_excludes_root_test_and_debug_helpers(path):
    assert prod_deploy.is_excluded(path)


@pytest.mark.parametrize(
    "directory_name",
    [
        ".npm-cache",
        ".npm-bootstrap-cache",
        ".pnpm-store",
        ".tools",
        ".uv-cache",
        ".uv-tools",
        ".uv-tools-bin",
    ],
)
def test_release_bundle_excludes_local_dependency_and_tool_caches(directory_name):
    assert prod_deploy.is_excluded(
        Path("apps/automation-service") / directory_name / "cache-entry"
    )


def test_remote_run_drains_output_before_waiting_for_exit_status(capsys):
    stdin = _FakeStdin()
    channel = _FakeChannel([b"line-1\n", b"line-2"], [b"warn-1\n"])
    host = prod_deploy.RemoteHost("test-host", {"host": "example.com"}, dry_run=False)
    host.client = _FakeClient(channel, stdin, expected_timeout=30)

    out, err, code = host.run("echo test", timeout=30)

    captured = capsys.readouterr()
    assert stdin.closed is True
    assert out == "line-1\nline-2"
    assert err == "warn-1\n"
    assert code == 0
    assert "line-1" in captured.out
    assert "line-2" in captured.out
    assert "warn-1" in captured.err


def test_remote_host_rejects_unknown_ssh_host_keys(monkeypatch):
    client = _HostKeyCheckingClient()
    monkeypatch.setattr(prod_deploy.paramiko, "SSHClient", lambda: client)

    with prod_deploy.RemoteHost(
        "production-host",
        {"host": "example.com", "username": "deploy"},
        dry_run=False,
    ):
        pass

    assert client.loaded_system_keys is True
    assert isinstance(client.policy, prod_deploy.paramiko.RejectPolicy)
    assert client.connect_kwargs["hostname"] == "example.com"
    assert client.closed is True


def test_remote_host_rejects_ambiguous_key_and_password_before_opening_client(monkeypatch):
    monkeypatch.setattr(
        prod_deploy.paramiko,
        "SSHClient",
        lambda: (_ for _ in ()).throw(AssertionError("client must not be opened")),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="must not combine"):
        with prod_deploy.RemoteHost(
            "production-host",
            {
                "host": "example.com",
                "username": "deploy",
                "key_filename": "id_ed25519",
                "password": "must-not-be-used",
            },
            dry_run=False,
        ):
            pass


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for release revision contract")
def test_release_revision_requires_a_real_clean_git_worktree(tmp_path):
    repository = tmp_path / "release-source"
    repository.mkdir()

    with pytest.raises(prod_deploy.ProductionPreflightError, match="real Git repository"):
        prod_deploy.validate_clean_release_revision(repository)

    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    (repository / "release.txt").write_text("reviewed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repository), "add", "release.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repository),
            "-c",
            "user.name=Release Test",
            "-c",
            "user.email=release-test@example.invalid",
            "commit",
            "-q",
            "-m",
            "reviewed release",
        ],
        check=True,
    )

    revision = prod_deploy.validate_clean_release_revision(repository)
    assert len(revision) in {40, 64}

    (repository / "unreviewed.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(prod_deploy.ProductionPreflightError, match="clean worktree"):
        prod_deploy.validate_clean_release_revision(repository)


def test_release_transaction_rechecks_that_the_worktree_revision_did_not_change(
    monkeypatch,
):
    monkeypatch.setattr(
        prod_deploy,
        "validate_clean_release_revision",
        lambda: "d" * 40,
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="source revision changed"):
        prod_deploy._assert_release_worktree_unchanged("c" * 40)


def test_frontend_remote_cutover_has_strict_rollback_for_files_and_nginx(
    monkeypatch,
    tmp_path,
):
    nginx_config = tmp_path / "secure-nginx.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    recording = _RecordingRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(
        prod_deploy,
        "sync_frontend_to_staged",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(prod_deploy, "run_local", lambda *_args, **_kwargs: None)
    config = {
        "us_frontend": {
            "nginx_config_source": str(nginx_config),
            "user_web_root": "/var/www/user-web",
            "admin_web_root": "/var/www/admin-web",
        }
    }

    rollback = prod_deploy.deploy_frontend(
        config,
        skip_frontend_build=False,
        dry_run=False,
        release_revision="c" * 40,
    )

    command = recording.commands[-1][0]
    assert "rollback()" in command
    assert "trap rollback ERR" in command
    assert "USER_BACKED_UP=1" in command
    assert "ADMIN_BACKED_UP=1" in command
    assert "NGINX_CHANGE_STARTED=1" in command
    assert "cutover-complete" in command
    assert "release-transaction" in command
    assert "user-live-identity" in command
    assert "admin-live-identity" in command
    assert "trap - ERR" in command
    assert command.index("trap rollback ERR") < command.index('mv "$USER_STAGE"')

    rollback()

    rollback_command, rollback_options = recording.commands[-1]
    assert rollback_options["check"] is False
    assert "refusing stale rollback" in rollback_command
    assert "nginx-deployed-sha256" in rollback_command
    assert "user-web-failed-" in rollback_command
    assert "admin-web-failed-" in rollback_command


@pytest.mark.parametrize(
    ("exit_code", "message"),
    [
        (1, "prior files/Nginx state was restored"),
        (70, "rollback did not complete"),
    ],
)
def test_frontend_cutover_reports_observed_rollback_outcome(
    monkeypatch,
    tmp_path,
    exit_code,
    message,
):
    nginx_config = tmp_path / "secure-nginx.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    recording = _RecordingRemote()

    def run_with_exit_code(command, **kwargs):
        recording.commands.append((command, kwargs))
        return "", "", exit_code

    recording.run = run_with_exit_code
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(
        prod_deploy,
        "sync_frontend_to_staged",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(prod_deploy, "run_local", lambda *_args, **_kwargs: None)
    config = {
        "us_frontend": {
            "nginx_config_source": str(nginx_config),
            "user_web_root": "/var/www/user-web",
            "admin_web_root": "/var/www/admin-web",
        }
    }

    with pytest.raises(prod_deploy.CommandError, match=message):
        prod_deploy.deploy_frontend(
            config,
            skip_frontend_build=False,
            dry_run=False,
            release_revision="c" * 40,
        )

    assert recording.commands[-1][1]["check"] is False


def test_backend_deploy_requires_runtime_and_mandatory_monitoring_health_without_public_http(
    monkeypatch,
    tmp_path,
):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _RecordingRemote()

    def _run_with_monitoring(command, **kwargs):
        recording.commands.append((command, kwargs))
        if "MONITORING_ENABLED" in command:
            return "true\n", "", 0
        return "", "", 0

    recording.run = _run_with_monitoring
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["backend"],
            "infra_services": [],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    prod_deploy.deploy_backend(
        config,
        dry_run=False,
        deploy_mode="backend",
        release_revision="c" * 40,
    )

    commands = recording.commands
    runtime_health_command, runtime_options = next(
        entry for entry in commands if "runtime containers did not become healthy" in entry[0]
    )
    assert "docker inspect" in runtime_health_command
    assert "xianyu-admin-backend" in runtime_health_command
    assert "State.Health.Status" in runtime_health_command
    assert runtime_options["timeout"] == 330
    assert "http://" not in runtime_health_command

    monitoring_indices = [
        index for index, entry in enumerate(commands)
        if "monitoring containers did not become healthy" in entry[0]
    ]
    monitoring_checks = [commands[index] for index in monitoring_indices]
    assert len(monitoring_checks) == 2
    for monitoring_command, options in monitoring_checks:
        for container in prod_deploy.MONITORING_CONTAINERS:
            assert container in monitoring_command
        assert 'if [ -z "$status" ] || [ "$status" = missing ]' in monitoring_command
        assert options["timeout"] == 330
        assert "http://" not in monitoring_command

    activation_index = next(
        index for index, (command, _options) in enumerate(commands)
        if ".release-revision" in command and "rollback_activation" in command
    )
    runtime_index = commands.index((runtime_health_command, runtime_options))
    assert monitoring_indices[0] < activation_index < runtime_index < monitoring_indices[1]


def test_successful_backend_deploy_retains_version_guarded_post_gate_rollback(
    monkeypatch,
    tmp_path,
):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _RecordingRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["backend"],
            "infra_services": [],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    rollback = prod_deploy.deploy_backend(
        config,
        dry_run=False,
        deploy_mode="backend",
        release_revision="c" * 40,
    )
    rollback()

    rollback_command, rollback_options = recording.commands[-1]
    assert rollback_options["check"] is False
    assert "live backend revision changed; refusing stale rollback" in rollback_command
    assert "live backend transaction changed; refusing stale rollback" in rollback_command
    assert ".release-revision" in rollback_command
    assert ".release-transaction" in rollback_command
    assert " up -d --no-deps --force-recreate backend" in rollback_command
    assert "docker inspect" in rollback_command


def test_full_backend_deploy_preflights_and_health_gates_mandatory_monitoring(
    monkeypatch,
    tmp_path,
):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _RecordingRemote()

    def _run_with_monitoring(command, **kwargs):
        recording.commands.append((command, kwargs))
        if "MONITORING_ENABLED" in command:
            return "true\n", "", 0
        return "", "", 0

    recording.run = _run_with_monitoring
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": [
                "automation",
                "automation-worker",
                "crawler-service",
                "crawler-worker",
                "backend",
            ],
            "infra_services": [],
            "runtime_services": [
                "automation",
                "automation-worker",
                "crawler-service",
                "crawler-worker",
                "backend",
            ],
            "backend_target_services": ["backend"],
        }
    }

    release_revision = "c" * 40
    release_id = "release-20260711-01"
    evidence_sha256 = "e" * 64
    prod_deploy.deploy_backend(
        config,
        dry_run=False,
        deploy_mode="all",
        release_revision=release_revision,
        release_id=release_id,
        migration_evidence_sha256=evidence_sha256,
    )

    commands = [command for command, _options in recording.commands]
    extract_command = commands[0]
    assert ".release-" in extract_command
    assert "release staging path collision" in extract_command
    assert ".env-hold-" in extract_command
    assert "readlink -f" in extract_command
    assert "resolved_project_parent" in extract_command
    assert extract_command.count("[ -L ") >= 5
    assert "mkdir -p" in extract_command
    preflight_index = next(
        index for index, command in enumerate(commands)
        if "scripts/production-preflight.sh" in command
    )
    deploy_index = next(
        index for index, command in enumerate(commands)
        if "docker-compose.monitoring.yml" in command and " up -d " in command
    )
    assert preflight_index < deploy_index
    assert ".release-" in commands[preflight_index]
    assert release_revision in commands[preflight_index]
    assert release_id in commands[preflight_index]
    assert evidence_sha256 in commands[preflight_index]
    activation_index = next(
        index for index, command in enumerate(commands)
        if ".previous-" in command and ".env-hold-" in command and ".release-revision" in command
    )
    assert preflight_index < activation_index < deploy_index
    activation_command = commands[activation_index]
    assert "rollback_activation" in activation_command
    assert "trap rollback_activation ERR" in activation_command
    assert "rollback_activation 129" in activation_command
    assert "rollback_activation 130" in activation_command
    assert "rollback_activation 143" in activation_command
    assert "trap - ERR HUP INT TERM" in activation_command
    deploy_command = commands[deploy_index]
    assert "--profile monitoring" in deploy_command
    for service in prod_deploy.MONITORING_SERVICES:
        assert service in deploy_command

    runtime_health_command, runtime_options = recording.commands[-2]
    for container in (
        "xianyu-automation-service",
        "xianyu-automation-worker",
        "xianyu-crawler-service",
        "xianyu-crawler-worker",
        "xianyu-admin-backend",
    ):
        assert container in runtime_health_command
    assert "State.Health.Status" in runtime_health_command
    assert runtime_options["timeout"] == 330

    monitoring_health_command, options = recording.commands[-1]
    for container in prod_deploy.MONITORING_CONTAINERS:
        assert container in monitoring_health_command
    assert "State.Health.Status" in monitoring_health_command
    assert options["timeout"] == 330


@pytest.mark.skipif(BASH is None, reason="Bash is required for generated-command syntax checks")
def test_generated_backend_remote_commands_are_valid_bash(monkeypatch, tmp_path):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _RecordingRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["mysql", "backend"],
            "infra_services": ["mysql"],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    prod_deploy.deploy_backend(
        config,
        dry_run=False,
        deploy_mode="all",
        release_revision="c" * 40,
    )

    scripts = []
    for command, _options in recording.commands:
        if not command.startswith("bash -lc "):
            continue
        arguments = shlex.split(command, posix=True)
        assert arguments[:2] == ["bash", "-lc"]
        scripts.append(arguments[2])

    assert scripts
    for script in scripts:
        completed = subprocess.run(
            [BASH, "-n", "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr


@pytest.mark.skipif(BASH is None, reason="Bash is required for generated-command syntax checks")
def test_generated_frontend_cutover_and_post_gate_rollback_are_valid_bash(
    monkeypatch,
    tmp_path,
):
    nginx_config = tmp_path / "secure-nginx.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    recording = _RecordingRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(
        prod_deploy,
        "sync_frontend_to_staged",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(prod_deploy, "run_local", lambda *_args, **_kwargs: None)
    config = {
        "us_frontend": {
            "nginx_config_source": str(nginx_config),
            "user_web_root": "/var/www/user-web",
            "admin_web_root": "/var/www/admin-web",
        }
    }

    rollback = prod_deploy.deploy_frontend(
        config,
        skip_frontend_build=False,
        dry_run=False,
        release_revision="c" * 40,
    )
    rollback()

    scripts = []
    for command, _options in recording.commands:
        if not command.startswith("bash -lc "):
            continue
        arguments = shlex.split(command, posix=True)
        assert arguments[:2] == ["bash", "-lc"]
        scripts.append(arguments[2])

    assert len(scripts) == 3
    for script in scripts:
        completed = subprocess.run(
            [BASH, "-n", "-c", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("flag", ["skip_frontend_build", "skip_smoke"])
def test_main_rejects_release_verification_bypasses_outside_dry_run(monkeypatch, flag):
    args = SimpleNamespace(
        config="local.json",
        target="all",
        skip_frontend_build=flag == "skip_frontend_build",
        skip_smoke=flag == "skip_smoke",
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=None,
        release_id=None,
    )
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(
        prod_deploy,
        "load_config",
        lambda *_args, **_kwargs: pytest.fail("release config must not be read after a bypass attempt"),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="dry-run"):
        prod_deploy.main()


def test_frontend_deploy_rejects_skipping_build_for_real_cutover():
    with pytest.raises(prod_deploy.ProductionPreflightError, match="dry-run"):
        prod_deploy.deploy_frontend(
            {"us_frontend": {}},
            skip_frontend_build=True,
            dry_run=False,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"user_web_root": "/"}, "user_web_root"),
        ({"user_web_root": "/var/www"}, "user_web_root"),
        ({"user_web_root": "/var/www/user-web/../admin-web"}, "user_web_root"),
        ({"admin_web_root": "/var/www/user-web"}, "must not overlap"),
        ({"backup_root": "/var/www/user-web/backups"}, "must not overlap"),
        ({"release_root": "/tmp/releases"}, "release_root"),
        ({"nginx_site_path": "/etc/passwd"}, "nginx_site_path"),
    ],
)
def test_frontend_deploy_rejects_unsafe_or_overlapping_remote_paths_before_build(
    monkeypatch,
    overrides,
    message,
):
    frontend = {
        "user_web_root": "/var/www/user-web",
        "admin_web_root": "/var/www/admin-web",
        **overrides,
    }
    monkeypatch.setattr(
        prod_deploy,
        "run_local",
        lambda *_args, **_kwargs: pytest.fail("unsafe paths must fail before build"),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match=message):
        prod_deploy.deploy_frontend(
            {"us_frontend": frontend},
            skip_frontend_build=False,
            dry_run=False,
            release_revision="c" * 40,
        )


@pytest.mark.parametrize(
    "project_dir",
    [
        "/",
        "relative/project",
        "/home/ubuntu/../project",
        "/etc/xianyupilot",
        "/var/lib/docker/xianyupilot",
        "/home",
    ],
)
def test_backend_deploy_rejects_unsafe_remote_project_paths(monkeypatch, tmp_path, project_dir):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)

    with pytest.raises(prod_deploy.ProductionPreflightError, match="project_dir"):
        prod_deploy.deploy_backend(
            {"china_backend": {"project_dir": project_dir}},
            dry_run=False,
            release_revision="c" * 40,
        )


def test_absolute_compose_env_inside_project_is_preserved_across_source_cutover():
    project_dir = "/home/ubuntu/project"
    in_tree_env = "/home/ubuntu/project/secrets/.env.production"
    external_env = "/etc/xianyupilot/.env.production"

    assert prod_deploy._validated_remote_compose_env(project_dir, in_tree_env) == (
        in_tree_env,
        False,
    )
    assert prod_deploy._validated_remote_compose_env(project_dir, external_env) == (
        external_env,
        True,
    )


def test_backend_deploy_requires_the_exact_release_revision_before_build(monkeypatch):
    monkeypatch.setattr(
        prod_deploy,
        "sync_backend_to_staged",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sync must not be called")),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="release revision"):
        prod_deploy.deploy_backend(
            {"china_backend": {"project_dir": "/home/ubuntu/project"}},
            dry_run=False,
            release_revision=None,
        )


def test_backend_deploy_rolls_source_and_runtime_back_after_cutover_failure(monkeypatch, tmp_path):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _FailingDeployRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["backend"],
            "infra_services": [],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    with pytest.raises(prod_deploy.CommandError, match="simulated deploy failure"):
        prod_deploy.deploy_backend(
            config,
            dry_run=False,
            deploy_mode="all",
            release_revision="c" * 40,
        )

    rollback_command, rollback_options = recording.commands[-1]
    assert rollback_options["check"] is False
    assert ".previous-" in rollback_command
    assert ".failed-" in rollback_command
    assert "set -Eeuo pipefail" in rollback_command
    assert rollback_command.index(".previous-") < rollback_command.index("cd /home/ubuntu/project")
    assert " up -d --build --force-recreate backend" in rollback_command
    assert "docker inspect" in rollback_command


def test_backend_health_failure_rolls_source_back_and_rebuilds_old_runtime(monkeypatch, tmp_path):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _FailingRuntimeHealthRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["backend"],
            "infra_services": [],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    with pytest.raises(prod_deploy.CommandError, match="simulated health failure"):
        prod_deploy.deploy_backend(
            config,
            dry_run=False,
            deploy_mode="backend",
            release_revision="c" * 40,
        )

    rollback_command, rollback_options = recording.commands[-1]
    assert rollback_options["check"] is False
    assert "mv /home/ubuntu/project.previous-" in rollback_command
    assert " up -d --no-deps --force-recreate backend" in rollback_command


def test_backend_reports_when_old_source_runtime_rollback_itself_fails(monkeypatch, tmp_path):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _FailingDeployAndRollbackRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["backend"],
            "infra_services": [],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    with pytest.raises(prod_deploy.CommandError, match="rollback did not complete"):
        prod_deploy.deploy_backend(
            config,
            dry_run=False,
            deploy_mode="all",
            release_revision="c" * 40,
        )


def test_full_backend_rollback_reapplies_old_infrastructure_compose(monkeypatch, tmp_path):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _FailingDeployRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["mysql", "backend"],
            "infra_services": ["mysql"],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        }
    }

    with pytest.raises(prod_deploy.CommandError, match="simulated deploy failure"):
        prod_deploy.deploy_backend(
            config,
            dry_run=False,
            deploy_mode="all",
            release_revision="c" * 40,
        )

    rollback_command = recording.commands[-1][0]
    old_source_position = rollback_command.index("mv /home/ubuntu/project.previous-")
    infra_position = rollback_command.index(" up -d mysql")
    runtime_position = rollback_command.index(" up -d --build --force-recreate backend")
    assert old_source_position < infra_position < runtime_position


def test_public_backend_health_failure_uses_the_same_atomic_rollback(monkeypatch, tmp_path):
    bundle = tmp_path / "backend.tar.gz"
    bundle.write_bytes(b"placeholder")
    recording = _RecordingRemote()
    monkeypatch.setattr(prod_deploy, "RemoteHost", lambda *_args, **_kwargs: recording)
    monkeypatch.setattr(prod_deploy, "sync_backend_to_staged", lambda *a, **kw: None)

    checked_urls = []

    def fail_public_health(url, **_kwargs):
        checked_urls.append(url)
        raise prod_deploy.CommandError("simulated public health failure")

    monkeypatch.setattr(prod_deploy, "wait_for_http_ok", fail_public_health)
    config = {
        "china_backend": {
            "project_dir": "/home/ubuntu/project",
            "services": ["backend"],
            "infra_services": [],
            "runtime_services": ["backend"],
            "backend_target_services": ["backend"],
        },
        "smoke": {
            "user_frontend_base": "https://www.example.com",
            "admin_frontend_base": "https://admin.example.com",
        },
    }

    with pytest.raises(prod_deploy.CommandError, match="simulated public health failure"):
        prod_deploy.deploy_backend(
            config,
            dry_run=False,
            deploy_mode="backend",
            release_revision="c" * 40,
        )

    assert checked_urls == ["https://www.example.com/api/health"]
    rollback_command, rollback_options = recording.commands[-1]
    assert rollback_options["check"] is False
    assert "mv /home/ubuntu/project.previous-" in rollback_command
    assert " up -d --no-deps --force-recreate backend" in rollback_command


def test_backend_deploy_rejects_legacy_public_http_health_url_before_build(monkeypatch):
    monkeypatch.setattr(
        prod_deploy,
        "sync_backend_to_staged",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("sync must not be called")),
    )
    config = {
        "china_backend": {
            "health_urls": ["http://203.0.113.10:18080/api/health"],
        }
    }

    with pytest.raises(prod_deploy.ProductionPreflightError, match="HTTPS URLs only"):
        prod_deploy.deploy_backend(
            config,
            dry_run=False,
            release_revision="c" * 40,
        )


def test_managed_infrastructure_guard_blocks_implicit_image_migrations():
    script = prod_deploy._infrastructure_image_guard_script(
        ["mysql", "redis", "crawler-postgres"]
    )

    assert script is not None
    assert "mysql:8.4.10" in script
    assert "redis:7.4.9-alpine" in script
    assert "postgres:16.14-alpine" in script
    assert script.count("exit 42") == 3
    assert script.index("docker inspect") < script.index("exit 42")


def test_docker_release_commands_ignore_ambient_compose_and_remote_daemon_controls():
    expected = (
        "unset COMPOSE_FILE COMPOSE_PROJECT_NAME COMPOSE_PROFILES "
        "COMPOSE_ENV_FILES DOCKER_HOST DOCKER_CONTEXT"
    )

    assert expected in prod_deploy.DOCKER_ENV_GUARD
    assert "export DOCKER_CONTEXT=default" in prod_deploy.DOCKER_ENV_GUARD
    assert expected in prod_deploy._container_health_wait_script(
        ["xianyu-admin-backend"], "runtime"
    )
    assert expected in prod_deploy._infrastructure_image_guard_script(["mysql"])
    preflight = (prod_deploy.REPO_ROOT / "scripts/production-preflight.sh").read_text(
        encoding="utf-8"
    )
    assert expected in preflight
    assert "export DOCKER_CONTEXT=default" in preflight


def test_remote_run_raises_on_remote_timeout(monkeypatch):
    stdin = _FakeStdin()
    channel = _FakeChannel([], [])
    host = prod_deploy.RemoteHost("test-host", {"host": "example.com"}, dry_run=False)
    host.client = _FakeClient(channel, stdin, expected_timeout=1)

    channel.exit_status_ready = lambda: False
    ticks = iter([0, 2])
    monkeypatch.setattr(prod_deploy.time, "time", lambda: next(ticks, 2))

    with pytest.raises(prod_deploy.CommandError, match="timed out"):
        host.run("echo test", timeout=1)

    assert channel.closed is True


def test_backend_bundle_excludes_secret_like_file_without_touching_it(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    app_root.mkdir(parents=True)
    (app_root / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    secret_value = "this-value-must-never-appear-in-errors"
    (app_root / ".env.production").write_text(
        f"ADMIN_JWT_SECRET={secret_value}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/core-api"])

    bundle = prod_deploy.create_backend_bundle()

    with tarfile.open(bundle, "r:gz") as archive:
        names = {member.name.rstrip("/") for member in archive.getmembers()}
    assert "apps/core-api/Dockerfile" in names
    assert "apps/core-api/.env.production" not in names
    assert (app_root / ".env.production").read_text(encoding="utf-8") == (
        f"ADMIN_JWT_SECRET={secret_value}\n"
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "captures/login.har",
        "captures/network_dump.json",
        "captures/detail_response.json",
        "login-body.json",
        "login_body.json",
        "login-resp.json",
        "login_resp.json",
        "login_capture.json",
        "reset-admin-pwd.sql",
        "runtime/session_token.txt",
        "runtime/cookies.json",
        "runtime/storage-state.json",
        ".deploy.prod.json",
        "runtime/private.key",
        "runtime/client.pfx",
        ".npmrc",
    ],
)
def test_backend_bundle_excludes_secret_bearing_filenames(
    monkeypatch,
    tmp_path,
    relative_path,
):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    sensitive_path = app_root / relative_path
    sensitive_path.parent.mkdir(parents=True, exist_ok=True)
    sensitive_path.write_text("sensitive-value-must-not-leak\n", encoding="utf-8")

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/core-api"])

    bundle = prod_deploy.create_backend_bundle()

    with tarfile.open(bundle, "r:gz") as archive:
        names = {member.name.rstrip("/") for member in archive.getmembers()}
    assert f"apps/core-api/{relative_path}" not in names
    assert sensitive_path.read_text(encoding="utf-8") == "sensitive-value-must-not-leak\n"


def test_backend_bundle_secret_preflight_detects_literal_config_secret_without_leaking_it(
    monkeypatch,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    app_root.mkdir(parents=True)
    secret_value = "prod-secret-with-at-least-thirty-two-characters"
    (app_root / "unsafe.yml").write_text(
        f'ADMIN_JWT_SECRET: "{secret_value}"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/core-api"])

    with pytest.raises(prod_deploy.SecretPreflightError) as exc_info:
        prod_deploy.create_backend_bundle()

    message = str(exc_info.value)
    assert "apps/core-api/unsafe.yml" in message.replace("\\", "/")
    assert "literal secret assignment" in message
    assert secret_value not in message


def test_backend_bundle_secret_preflight_rejects_short_literal_password(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    app_root.mkdir(parents=True)
    (app_root / "unsafe.json").write_text(
        '{\n  "password": "short-pass"\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/core-api"])

    with pytest.raises(prod_deploy.SecretPreflightError, match="literal secret assignment"):
        prod_deploy.create_backend_bundle()


def test_backend_bundle_uses_allowlist_and_omits_logs_and_temporary_artifacts(
    monkeypatch,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    (app_root / "src").mkdir(parents=True)
    (app_root / "src" / "Main.java").write_text("class Main {}\n", encoding="utf-8")
    (app_root / "debug.log").write_text("debug\n", encoding="utf-8")
    (app_root / "temp" / "session.json").parent.mkdir(parents=True)
    (app_root / "temp" / "session.json").write_text("{}\n", encoding="utf-8")
    (app_root / "build.tmp").write_text("temp\n", encoding="utf-8")
    for cache_name in (
        ".npm-cache",
        ".npm-bootstrap-cache",
        ".pnpm-store",
        ".tools",
        ".uv-cache",
        ".uv-tools",
        ".uv-tools-bin",
    ):
        cache_file = app_root / cache_name / "large-cache-entry.bin"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_bytes(b"must-not-ship")
    (repo_root / "unlisted.txt").write_text("must not ship\n", encoding="utf-8")
    (repo_root / ".env.production.example").write_text(
        "ADMIN_JWT_SECRET=replace-with-a-production-secret\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")
    monkeypatch.setattr(
        prod_deploy,
        "BACKEND_BUNDLE_ITEMS",
        ["apps/core-api", ".env.production.example"],
    )

    bundle = prod_deploy.create_backend_bundle()

    with tarfile.open(bundle, "r:gz") as archive:
        names = {member.name.rstrip("/") for member in archive.getmembers()}
    assert "apps/core-api/src/Main.java" in names
    assert ".env.production.example" in names
    assert "unlisted.txt" not in names
    assert "apps/core-api/debug.log" not in names
    assert "apps/core-api/temp" not in names
    assert "apps/core-api/temp/session.json" not in names
    assert "apps/core-api/build.tmp" not in names
    assert not any("large-cache-entry.bin" in name for name in names)


def test_production_preflight_rejects_public_plaintext_http_upstream(tmp_path):
    nginx_config = tmp_path / "public-http.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://203.0.113.10:18080/api/; } }\n",
        encoding="utf-8",
    )

    with pytest.raises(prod_deploy.ProductionPreflightError) as exc_info:
        prod_deploy.validate_nginx_transport_security(nginx_config)

    message = str(exc_info.value)
    assert "public plaintext HTTP upstream" in message
    assert "HTTPS with certificate verification" in message
    assert "VPN/private address" in message


def test_production_preflight_rejects_unverified_public_https_upstream(tmp_path):
    nginx_config = tmp_path / "unverified-https.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass https://origin.example.com/api/; } }\n",
        encoding="utf-8",
    )

    with pytest.raises(prod_deploy.ProductionPreflightError) as exc_info:
        prod_deploy.validate_nginx_transport_security(nginx_config)

    message = str(exc_info.value)
    assert "proxy_ssl_verify on" in message
    assert "proxy_ssl_server_name on" in message


def test_production_preflight_requires_https_verification_in_each_effective_scope(tmp_path):
    nginx_config = tmp_path / "mixed-https.conf"
    nginx_config.write_text(
        """
server {
    location /verified/ {
        proxy_pass https://verified.example.com/;
        proxy_ssl_verify on;
        proxy_ssl_server_name on;
        proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
    }
    location /unverified/ {
        proxy_pass https://unverified.example.com/;
    }
}
""",
        encoding="utf-8",
    )

    with pytest.raises(prod_deploy.ProductionPreflightError) as exc_info:
        prod_deploy.validate_nginx_transport_security(nginx_config)

    message = str(exc_info.value)
    assert "unverified.example.com" in message
    assert "host verified.example.com" not in message


@pytest.mark.parametrize(
    "config_text",
    [
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        """
server {
    proxy_ssl_verify on;
    proxy_ssl_server_name on;
    proxy_ssl_trusted_certificate /etc/ssl/certs/ca-certificates.crt;
    location /api/ { proxy_pass https://origin.example.com/api/; }
}
""",
    ],
)
def test_production_preflight_accepts_verified_https_or_private_vpn_origin(
    tmp_path,
    config_text,
):
    nginx_config = tmp_path / "secure-origin.conf"
    nginx_config.write_text(config_text, encoding="utf-8")

    prod_deploy.validate_nginx_transport_security(nginx_config)


def test_origin_tunnel_service_template_rejects_root_or_missing_host_pinning(tmp_path):
    service = tmp_path / "unsafe-tunnel.service"
    service.write_text(
        """
[Service]
User=root
ExecStart=/usr/bin/ssh -N -L 127.0.0.1:18081:127.0.0.1:18080 origin.example.com
""",
        encoding="utf-8",
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="unsafe") as exc_info:
        prod_deploy.validate_origin_tunnel_service_template(service)

    message = str(exc_info.value)
    assert "User=xianyupilot-tunnel" in message
    assert "StrictHostKeyChecking=yes" in message
    assert "forbidden User=root" in message


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "localhost", "[::1]"])
def test_managed_origin_tunnel_detection_covers_loopback_aliases(tmp_path, host):
    nginx_config = tmp_path / "loopback.conf"
    nginx_config.write_text(
        f"server {{ location /api/ {{ proxy_pass http://{host}:18081/api/; }} }}\n",
        encoding="utf-8",
    )

    assert prod_deploy.nginx_uses_managed_origin_tunnel(nginx_config) is True


@pytest.mark.parametrize(
    "frontend",
    [
        {"origin_tunnel_service": "tunnel.service; reboot"},
        {"origin_tunnel_health_url": "http://169.254.169.254/latest/meta-data"},
        {"origin_tunnel_health_url": "http://127.0.0.1:18081/api/health?token=x"},
    ],
)
def test_origin_tunnel_runtime_check_rejects_command_injection_and_remote_urls(frontend):
    with pytest.raises(prod_deploy.ProductionPreflightError):
        prod_deploy._validated_origin_tunnel_runtime(frontend)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.example.com",
        "https://user:secret@example.com",
        "https://example.com/app",
        "https://example.com?token=secret",
    ],
)
def test_public_smoke_origins_require_clean_https_origins(url):
    with pytest.raises(prod_deploy.ProductionPreflightError):
        prod_deploy._validated_public_https_base(url, "smoke.user_frontend_base")


def test_production_preflight_rejects_dynamic_proxy_pass_it_cannot_verify(tmp_path):
    nginx_config = tmp_path / "dynamic-origin.conf"
    nginx_config.write_text(
        "server { set $origin http://example.com; location / { proxy_pass $origin; } }\n",
        encoding="utf-8",
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="cannot verify"):
        prod_deploy.validate_nginx_transport_security(nginx_config)


def test_production_preflight_fails_closed_on_unterminated_nginx_directive(tmp_path):
    nginx_config = tmp_path / "malformed.conf"
    nginx_config.write_text(
        "server { location / { proxy_pass http://203.0.113.10:18080 } }\n",
        encoding="utf-8",
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="unterminated directive"):
        prod_deploy.validate_nginx_transport_security(nginx_config)


def test_preflight_only_does_not_load_real_deployment_credentials(
    monkeypatch,
    tmp_path,
    capsys,
):
    nginx_config = tmp_path / "secure-private-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://10.8.0.5:18080/api/; } }\n",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        config="must-not-be-read.json",
        target="all",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=True,
        nginx_config=str(nginx_config),
    )
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", [])
    monkeypatch.setattr(prod_deploy, "validate_migration_manifest", lambda **_kwargs: None)

    def fail_if_config_is_loaded(_path):
        raise AssertionError("preflight-only must not read deployment credentials")

    monkeypatch.setattr(prod_deploy, "load_config", fail_if_config_is_loaded)

    prod_deploy.main()

    output = capsys.readouterr().out
    assert "Production release source preflight passed" in output
    assert "migration evidence was not evaluated" in output


def test_preflight_only_binds_evidence_to_the_actual_clean_git_revision(monkeypatch):
    revision = "c" * 40
    captured = {}
    args = SimpleNamespace(
        config="must-not-be-read.json",
        target="all",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=True,
        nginx_config=None,
        migration_evidence=str((Path.cwd() / "migration-evidence.json").resolve()),
        release_id="release-20260711-01",
        release_revision=revision,
    )
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "_sha256_file", lambda _path: "f" * 64)
    monkeypatch.setattr(
        prod_deploy,
        "validate_migration_manifest",
        lambda **kwargs: captured.update(kwargs),
    )

    prod_deploy.main()

    assert captured["release_revision"] == revision


def test_preflight_only_rejects_an_asserted_revision_that_is_not_git_head(monkeypatch):
    args = SimpleNamespace(
        config="must-not-be-read.json",
        target="all",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=True,
        nginx_config=None,
        migration_evidence=str((Path.cwd() / "migration-evidence.json").resolve()),
        release_id="release-20260711-01",
        release_revision="d" * 40,
    )
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(
        prod_deploy,
        "validate_clean_release_revision",
        lambda: "c" * 40,
    )
    monkeypatch.setattr(
        prod_deploy,
        "validate_migration_manifest",
        lambda **_kwargs: pytest.fail("mismatched evidence must not be evaluated"),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="clean Git HEAD"):
        prod_deploy.main()


def test_main_blocks_insecure_origin_before_build_or_ssh(monkeypatch, tmp_path):
    nginx_config = tmp_path / "unsafe-origin.conf"
    nginx_config.write_text(
        "server { location /api/ { proxy_pass http://203.0.113.10:18080/api/; } }\n",
        encoding="utf-8",
    )
    args = SimpleNamespace(
        config="local.json",
        target="frontend",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
    )
    config = {
        "us_frontend": {"nginx_config_source": str(nginx_config)},
    }
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "load_config", lambda _path: config)
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: "a" * 40)
    monkeypatch.setattr(prod_deploy, "validate_git_tracked_sensitive_paths", lambda: None)

    deploy_called = False

    def fail_if_deploy_starts(*_args, **_kwargs):
        nonlocal deploy_called
        deploy_called = True

    monkeypatch.setattr(prod_deploy, "deploy_frontend", fail_if_deploy_starts)

    with pytest.raises(prod_deploy.ProductionPreflightError, match="public plaintext"):
        prod_deploy.main()

    assert deploy_called is False


def test_main_binds_local_git_revision_to_evidence_and_remote_deploy(monkeypatch, tmp_path):
    revision = "c" * 40
    evidence = tmp_path / "migration-evidence.json"
    evidence.write_text("{}\n", encoding="utf-8")
    evidence_sha256 = prod_deploy._sha256_file(evidence)
    args = SimpleNamespace(
        config="local.json",
        target="backend",
        skip_frontend_build=False,
        skip_smoke=True,
        dry_run=True,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=str(evidence),
        release_id="release-20260711-01",
        release_revision=None,
    )
    captured = {}

    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(
        prod_deploy,
        "load_config",
        lambda _path: {"china_backend": {"project_dir": "/home/ubuntu/project"}},
    )
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)

    def capture_evidence(**kwargs):
        captured["evidence_revision"] = kwargs["release_revision"]

    def capture_deploy(_config, **kwargs):
        captured["deploy_revision"] = kwargs["release_revision"]
        captured["deploy_release_id"] = kwargs["release_id"]
        captured["deploy_evidence_sha256"] = kwargs["migration_evidence_sha256"]
        captured["verify_local_source"] = kwargs["verify_local_source"]

    monkeypatch.setattr(prod_deploy, "validate_migration_manifest", capture_evidence)
    monkeypatch.setattr(prod_deploy, "deploy_backend", capture_deploy)

    prod_deploy.main()

    assert captured == {
        "evidence_revision": revision,
        "deploy_revision": revision,
        "deploy_release_id": "release-20260711-01",
        "deploy_evidence_sha256": evidence_sha256,
        "verify_local_source": True,
    }


def test_main_rejects_migration_evidence_changed_during_validation(monkeypatch):
    revision = "c" * 40
    args = SimpleNamespace(
        config="local.json",
        target="backend",
        skip_frontend_build=False,
        skip_smoke=True,
        dry_run=True,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=str((Path.cwd() / "migration-evidence.json").resolve()),
        release_id="release-20260711-01",
        release_revision=None,
    )
    digests = iter(("a" * 64, "b" * 64))
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(
        prod_deploy,
        "load_config",
        lambda _path: {"china_backend": {"project_dir": "/home/ubuntu/project"}},
    )
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "validate_migration_manifest", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "_sha256_file", lambda _path: next(digests))
    monkeypatch.setattr(
        prod_deploy,
        "deploy_backend",
        lambda *_args, **_kwargs: pytest.fail("changed evidence must not deploy"),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="changed while"):
        prod_deploy.main()


def test_main_rejects_a_supplied_revision_that_is_not_the_clean_git_head(monkeypatch):
    args = SimpleNamespace(
        config="local.json",
        target="frontend",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=None,
        release_id=None,
        release_revision="d" * 40,
    )
    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "load_config", lambda _path: {"us_frontend": {}})
    monkeypatch.setattr(
        prod_deploy,
        "validate_clean_release_revision",
        lambda: "c" * 40,
    )
    monkeypatch.setattr(
        prod_deploy,
        "run_release_preflight",
        lambda **_kwargs: pytest.fail("revision mismatch must fail before release preflight"),
    )

    with pytest.raises(prod_deploy.ProductionPreflightError, match="clean Git HEAD"):
        prod_deploy.main()


def test_main_rolls_back_frontend_then_backend_when_final_smoke_fails(monkeypatch):
    revision = "c" * 40
    events = []
    args = SimpleNamespace(
        config="local.json",
        target="all",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=str((Path.cwd() / "migration-evidence.json").resolve()),
        release_id="release-20260711-01",
        release_revision=None,
    )
    config = {
        "china_backend": {"project_dir": "/home/ubuntu/project"},
        "us_frontend": {},
    }

    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "load_config", lambda _path: config)
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "validate_migration_manifest", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "_sha256_file", lambda _path: "f" * 64)

    def deploy_backend(*_args, **_kwargs):
        events.append("deploy-backend")
        return prod_deploy.DeploymentRollback(
            "China backend",
            lambda: events.append("rollback-backend"),
        )

    def deploy_frontend(*_args, **kwargs):
        assert kwargs["release_revision"] == revision
        assert kwargs["verify_local_source"] is True
        events.append("deploy-frontend")
        return prod_deploy.DeploymentRollback(
            "US frontend",
            lambda: events.append("rollback-frontend"),
        )

    def fail_smoke(*_args, **_kwargs):
        events.append("smoke")
        raise RuntimeError("simulated final smoke failure")

    monkeypatch.setattr(prod_deploy, "deploy_backend", deploy_backend)
    monkeypatch.setattr(prod_deploy, "deploy_frontend", deploy_frontend)
    monkeypatch.setattr(prod_deploy, "run_smoke_checks", fail_smoke)

    with pytest.raises(RuntimeError, match="simulated final smoke failure"):
        prod_deploy.main()

    assert events == [
        "deploy-backend",
        "deploy-frontend",
        "smoke",
        "rollback-frontend",
        "rollback-backend",
    ]


def test_main_rolls_back_completed_cutover_when_operator_interrupts_final_gate(monkeypatch):
    revision = "c" * 40
    events = []
    args = SimpleNamespace(
        config="local.json",
        target="frontend",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=None,
        release_id=None,
        release_revision=None,
    )
    config = {"us_frontend": {}}

    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "load_config", lambda _path: config)
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(
        prod_deploy,
        "deploy_frontend",
        lambda *_args, **_kwargs: prod_deploy.DeploymentRollback(
            "US frontend",
            lambda: events.append("rollback-frontend"),
        ),
    )
    monkeypatch.setattr(
        prod_deploy,
        "run_smoke_checks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    with pytest.raises(KeyboardInterrupt):
        prod_deploy.main()

    assert events == ["rollback-frontend"]


def test_all_target_smoke_checks_each_public_route_and_login_once(monkeypatch):
    requests = []
    config = {
        "smoke": {
            "user_frontend_base": "https://user.example.com",
            "admin_frontend_base": "https://admin.example.com",
            "user_credentials": {"username": "release-user", "password": "placeholder"},
            "admin_credentials": {"username": "release-admin", "password": "placeholder"},
        }
    }

    def request_text(url, method="GET", data=None, timeout=20, headers=None):
        requests.append((method, url))
        return 200, "ok"

    def request_json(url, method="GET", data=None, timeout=20, headers=None):
        requests.append((method, url))
        if url.endswith("/health"):
            return 200, "{}", {"code": 0, "data": {"status": "UP"}}
        if url.endswith("/login"):
            return 200, "{}", {"code": 0, "data": {"token": "smoke-token"}}
        assert headers == {"Authorization": "Bearer smoke-token"}
        return 200, "{}", {"code": 0, "data": {"id": 1}}

    monkeypatch.setattr(prod_deploy, "request_text", request_text)
    monkeypatch.setattr(prod_deploy, "request_json", request_json)

    prod_deploy.run_smoke_checks(config, target="all", dry_run=False)

    assert requests == [
        ("GET", "https://user.example.com/api/health"),
        ("GET", "https://admin.example.com/admin-api/health"),
        ("GET", "https://user.example.com/"),
        ("GET", "https://admin.example.com/"),
        ("POST", "https://user.example.com/api/login/login"),
        ("POST", "https://user.example.com/api/system/currentUser"),
        ("POST", "https://admin.example.com/admin-api/auth/login"),
        ("GET", "https://admin.example.com/admin-api/user/info"),
    ]


def test_smoke_login_requires_a_returned_access_token(monkeypatch):
    config = {
        "smoke": {
            "user_frontend_base": "https://user.example.com",
            "admin_frontend_base": "https://admin.example.com",
            "user_credentials": {"username": "release-user", "password": "placeholder"},
            "admin_credentials": {"userName": "release-admin", "password": "placeholder"},
        }
    }
    monkeypatch.setattr(
        prod_deploy,
        "request_text",
        lambda *_args, **_kwargs: (200, "ok"),
    )
    monkeypatch.setattr(
        prod_deploy,
        "request_json",
        lambda *_args, **_kwargs: (200, "{}", {"code": 200, "data": {}}),
    )

    with pytest.raises(RuntimeError, match="valid access token"):
        prod_deploy.run_smoke_checks(config, target="frontend", dry_run=False)


def test_smoke_login_requires_the_access_token_to_resolve_an_identity(monkeypatch):
    config = {
        "smoke": {
            "user_frontend_base": "https://user.example.com",
            "admin_frontend_base": "https://admin.example.com",
            "user_credentials": {"username": "release-user", "password": "placeholder"},
            "admin_credentials": {"userName": "release-admin", "password": "placeholder"},
        }
    }
    monkeypatch.setattr(
        prod_deploy,
        "request_text",
        lambda *_args, **_kwargs: (200, "ok"),
    )

    def request_json(url, **_kwargs):
        if url.endswith("/login"):
            return 200, "{}", {"code": 200, "data": {"token": "smoke-token"}}
        return 200, "{}", {"code": 200, "data": {}}

    monkeypatch.setattr(prod_deploy, "request_json", request_json)

    with pytest.raises(RuntimeError, match="no authenticated identity"):
        prod_deploy.run_smoke_checks(config, target="frontend", dry_run=False)


def test_main_rolls_back_backend_when_frontend_deploy_fails(monkeypatch):
    revision = "d" * 40
    events = []
    args = SimpleNamespace(
        config="local.json",
        target="all",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=str((Path.cwd() / "migration-evidence.json").resolve()),
        release_id="release-20260711-01",
        release_revision=None,
    )
    config = {
        "china_backend": {"project_dir": "/home/ubuntu/project"},
        "us_frontend": {},
    }

    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "load_config", lambda _path: config)
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "validate_migration_manifest", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "_sha256_file", lambda _path: "f" * 64)
    monkeypatch.setattr(
        prod_deploy,
        "deploy_backend",
        lambda *_args, **_kwargs: prod_deploy.DeploymentRollback(
            "China backend",
            lambda: events.append("rollback-backend"),
        ),
    )

    def fail_frontend(*_args, **_kwargs):
        raise prod_deploy.CommandError("simulated frontend deploy failure")

    monkeypatch.setattr(prod_deploy, "deploy_frontend", fail_frontend)
    monkeypatch.setattr(
        prod_deploy,
        "run_smoke_checks",
        lambda *_args, **_kwargs: pytest.fail("smoke must not run"),
    )

    with pytest.raises(prod_deploy.CommandError, match="simulated frontend deploy failure"):
        prod_deploy.main()

    assert events == ["rollback-backend"]


def test_main_attempts_every_rollback_and_reports_incomplete_compensation(monkeypatch):
    revision = "e" * 40
    events = []
    args = SimpleNamespace(
        config="local.json",
        target="all",
        skip_frontend_build=False,
        skip_smoke=False,
        dry_run=False,
        preflight_only=False,
        nginx_config=None,
        migration_evidence=str((Path.cwd() / "migration-evidence.json").resolve()),
        release_id="release-20260711-01",
        release_revision=None,
    )
    config = {
        "china_backend": {"project_dir": "/home/ubuntu/project"},
        "us_frontend": {},
    }

    monkeypatch.setattr(prod_deploy, "parse_args", lambda: args)
    monkeypatch.setattr(prod_deploy, "load_config", lambda _path: config)
    monkeypatch.setattr(prod_deploy, "validate_clean_release_revision", lambda: revision)
    monkeypatch.setattr(prod_deploy, "run_release_preflight", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "validate_migration_manifest", lambda **_kwargs: None)
    monkeypatch.setattr(prod_deploy, "_sha256_file", lambda _path: "f" * 64)
    monkeypatch.setattr(
        prod_deploy,
        "deploy_backend",
        lambda *_args, **_kwargs: prod_deploy.DeploymentRollback(
            "China backend",
            lambda: events.append("rollback-backend"),
        ),
    )

    def fail_frontend_rollback():
        events.append("rollback-frontend")
        raise prod_deploy.CommandError("simulated rollback transport failure")

    monkeypatch.setattr(
        prod_deploy,
        "deploy_frontend",
        lambda *_args, **_kwargs: prod_deploy.DeploymentRollback(
            "US frontend",
            fail_frontend_rollback,
        ),
    )
    monkeypatch.setattr(
        prod_deploy,
        "run_smoke_checks",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("smoke failed")),
    )

    with pytest.raises(prod_deploy.CommandError, match="US frontend") as exc_info:
        prod_deploy.main()

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert events == ["rollback-frontend", "rollback-backend"]


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for tracked-file contract")
def test_release_preflight_rejects_tracked_sensitive_file_without_reading_its_value(
    monkeypatch,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    secret_value = "tracked-secret-value-must-never-be-printed"
    (repo_root / ".env").write_text(
        f"ADMIN_JWT_SECRET={secret_value}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "-f", ".env"],
        check=True,
        capture_output=True,
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", [])

    with pytest.raises(prod_deploy.SecretPreflightError) as exc_info:
        prod_deploy.run_release_preflight(include_backend=True, nginx_config=None)

    message = str(exc_info.value)
    assert ".env" in message
    assert "tracked by Git" in message
    assert secret_value not in message


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required for tracked-file contract")
def test_release_preflight_scans_tracked_config_content_without_leaking_it(
    monkeypatch,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
    secret_value = "tracked-literal-secret-with-more-than-thirty-two-chars"
    config_path = repo_root / "release.yml"
    config_path.write_text(
        f'INTERNAL_API_TOKEN: "{secret_value}"\n',
        encoding="utf-8",
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "add", "release.yml"],
        check=True,
        capture_output=True,
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", [])

    with pytest.raises(prod_deploy.SecretPreflightError) as exc_info:
        prod_deploy.run_release_preflight(include_backend=True, nginx_config=None)

    message = str(exc_info.value)
    assert "release.yml" in message
    assert "literal secret assignment" in message
    assert secret_value not in message


def test_frontend_dist_bundle_excludes_secret_bearing_file_without_touching_it(
    monkeypatch,
    tmp_path,
):
    repo_root = tmp_path / "repo"
    dist_dir = repo_root / "apps" / "user-web" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("safe\n", encoding="utf-8")
    secret_value = "dist-secret-value-must-not-leak"
    (dist_dir / "session_token.txt").write_text(secret_value, encoding="utf-8")

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")

    bundle = prod_deploy.create_dist_bundle("user-web", dist_dir)

    with tarfile.open(bundle, "r:gz") as archive:
        names = {member.name.rstrip("/") for member in archive.getmembers()}
    assert "index.html" in names
    assert "session_token.txt" not in names
    assert (dist_dir / "session_token.txt").read_text(encoding="utf-8") == secret_value


def test_frontend_dist_bundle_omits_runtime_artifacts(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    dist_dir = repo_root / "apps" / "admin-web" / "dist"
    (dist_dir / "assets").mkdir(parents=True)
    (dist_dir / "index.html").write_text("safe\n", encoding="utf-8")
    (dist_dir / "assets" / "app.js").write_text("safe\n", encoding="utf-8")
    (dist_dir / "debug.log").write_text("debug\n", encoding="utf-8")
    (dist_dir / "temp" / "state.tmp").parent.mkdir(parents=True)
    (dist_dir / "temp" / "state.tmp").write_text("temp\n", encoding="utf-8")

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")

    bundle = prod_deploy.create_dist_bundle("admin-web", dist_dir)

    with tarfile.open(bundle, "r:gz") as archive:
        names = {member.name.rstrip("/") for member in archive.getmembers()}
    assert "index.html" in names
    assert "assets/app.js" in names
    assert "debug.log" not in names
    assert "temp" not in names
    assert "temp/state.tmp" not in names


def test_release_preflight_rejects_embedded_private_key_marker(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    app_root.mkdir(parents=True)
    private_material = "-----BEGIN PRIVATE KEY-----\nnot-a-real-key\n-----END PRIVATE KEY-----\n"
    (app_root / "notes.txt").write_text(private_material, encoding="utf-8")

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/core-api"])

    with pytest.raises(prod_deploy.SecretPreflightError) as exc_info:
        prod_deploy.preflight_backend_bundle_inputs()

    message = str(exc_info.value)
    assert "embedded private key" in message
    assert "BEGIN PRIVATE KEY" not in message


def test_release_preflight_allows_container_secret_file_indirection(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    compose = repo_root / "docker-compose.monitoring.yml"
    compose.parent.mkdir(parents=True)
    compose.write_text(
        "services:\n"
        "  grafana:\n"
        "    environment:\n"
        "      GF_SECURITY_ADMIN_PASSWORD__FILE: /run/secrets/grafana_admin_password\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        prod_deploy,
        "BACKEND_BUNDLE_ITEMS",
        ["docker-compose.monitoring.yml"],
    )

    prod_deploy.preflight_backend_bundle_inputs()


@pytest.mark.parametrize(
    "secret_path",
    ["/etc/passwd", "/run/secrets/../grafana-password", "relative-secret-file"],
)
def test_release_preflight_rejects_unsafe_secret_file_indirection(
    monkeypatch, tmp_path, secret_path
):
    repo_root = tmp_path / "repo"
    compose = repo_root / "docker-compose.monitoring.yml"
    compose.parent.mkdir(parents=True)
    compose.write_text(
        "services:\n"
        "  grafana:\n"
        "    environment:\n"
        f"      GF_SECURITY_ADMIN_PASSWORD__FILE: {secret_path}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        prod_deploy,
        "BACKEND_BUNDLE_ITEMS",
        ["docker-compose.monitoring.yml"],
    )

    with pytest.raises(prod_deploy.SecretPreflightError, match="literal secret assignment"):
        prod_deploy.preflight_backend_bundle_inputs()


def test_release_preflight_rejects_symbolic_links(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "core-api"
    app_root.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside release root\n", encoding="utf-8")
    link = app_root / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symbolic links are unavailable: {exc}")

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/core-api"])

    with pytest.raises(prod_deploy.SecretPreflightError, match="symbolic link"):
        prod_deploy.preflight_backend_bundle_inputs()


def test_bundle_preflight_does_not_scan_excluded_dependency_trees(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    app_root = repo_root / "apps" / "crawler-service"
    app_root.mkdir(parents=True)
    (app_root / "server.ts").write_text("export {};\n", encoding="utf-8")
    dependency_config = app_root / "node_modules" / "vendor" / "config.yml"
    dependency_config.parent.mkdir(parents=True)
    dependency_config.write_text(
        "vendor_token: this-is-a-long-vendor-test-fixture-value\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "BACKEND_BUNDLE_ITEMS", ["apps/crawler-service"])

    prod_deploy.preflight_backend_bundle_inputs()


def test_backend_bundle_fails_when_an_allowlisted_input_is_missing(monkeypatch, tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "apps" / "core-api").mkdir(parents=True)

    monkeypatch.setattr(prod_deploy, "REPO_ROOT", repo_root)
    monkeypatch.setattr(prod_deploy, "ARTIFACT_DIR", repo_root / ".deploy-prod-artifacts")
    monkeypatch.setattr(
        prod_deploy,
        "BACKEND_BUNDLE_ITEMS",
        ["apps/core-api", "docker-compose.yml"],
    )

    with pytest.raises(FileNotFoundError, match="docker-compose.yml"):
        prod_deploy.create_backend_bundle()
