from __future__ import annotations

import json
from pathlib import Path

import docker
import docker.errors

from app.domain.models import ExecutionResult, ExecutionSummary, TestCaseResult
from app.services.errors import SandboxError

IMAGE_TAG = "auto-project-tester-sandbox:latest"
DOCKERFILE_DIR = Path(__file__).resolve().parent.parent.parent / "docker"

INSTALL_TIMEOUT_SECONDS = 90
TEST_TIMEOUT_SECONDS = 60
MEM_LIMIT = "512m"
NANO_CPUS = 1_000_000_000  # 1 CPU
PIDS_LIMIT = 128
TIMEOUT_KILLED_EXIT_CODE = 124  # exit code of coreutils `timeout` when it kills the process

LOG_TAIL_CHARS = 4000


# docker.from_env() only respects DOCKER_HOST / the legacy default pipe. Docker Desktop
# on Windows commonly runs under the "desktop-linux" context instead, which uses a
# different named pipe -- from_env() doesn't know to look there. Try the sensible
# candidates in order rather than forcing the user to set DOCKER_HOST by hand.
_CANDIDATE_BASE_URLS = [
    None,  # docker.from_env() default (respects DOCKER_HOST if set)
    "npipe:////./pipe/dockerDesktopLinuxEngine",
    "npipe:////./pipe/docker_engine",
    "unix://var/run/docker.sock",
]


def _client() -> docker.DockerClient:
    last_error: Exception | None = None
    for base_url in _CANDIDATE_BASE_URLS:
        try:
            client = docker.from_env() if base_url is None else docker.DockerClient(base_url=base_url)
            client.ping()
            return client
        except Exception as exc:  # noqa: BLE001 - trying multiple candidates on purpose
            last_error = exc
            continue
    raise SandboxError(
        "Tidak bisa konek ke Docker daemon. Pastikan Docker Desktop jalan."
    ) from last_error


def ensure_sandbox_image(client: docker.DockerClient) -> None:
    try:
        client.images.get(IMAGE_TAG)
    except docker.errors.ImageNotFound:
        try:
            client.images.build(
                path=str(DOCKERFILE_DIR),
                dockerfile="sandbox.Dockerfile",
                tag=IMAGE_TAG,
                rm=True,
            )
        except docker.errors.BuildError as exc:
            raise SandboxError(f"Gagal build sandbox image: {exc}") from exc


def _disconnect_network(client: docker.DockerClient, container) -> None:
    container.reload()
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    for net_name in list(networks.keys()):
        try:
            client.networks.get(net_name).disconnect(container, force=True)
        except docker.errors.APIError:
            pass


def _parse_pytest_json_report(raw: str) -> tuple[ExecutionSummary, list[TestCaseResult]]:
    if not raw.strip():
        return ExecutionSummary(), []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ExecutionSummary(), []

    summary_data = data.get("summary", {})
    summary = ExecutionSummary(
        total=summary_data.get("total", summary_data.get("collected", 0)),
        passed=summary_data.get("passed", 0),
        failed=summary_data.get("failed", 0),
        errors=summary_data.get("error", 0),
        skipped=summary_data.get("skipped", 0),
        duration_seconds=data.get("duration", 0.0),
    )

    tests: list[TestCaseResult] = []
    for t in data.get("tests", []):
        outcome = t.get("outcome", "failed")
        if outcome not in ("passed", "failed", "error", "skipped"):
            outcome = "failed"
        message = None
        for phase in ("call", "setup", "teardown"):
            phase_data = t.get(phase) or {}
            if phase_data.get("longrepr"):
                message = str(phase_data["longrepr"])[:2000]
                break
        duration = sum((t.get(p) or {}).get("duration", 0.0) for p in ("setup", "call", "teardown"))
        tests.append(TestCaseResult(
            node_id=t.get("nodeid", "?"),
            outcome=outcome,
            duration=duration,
            message=message,
        ))

    return summary, tests


def run_in_sandbox(source_dir: Path) -> ExecutionResult:
    """Runs the (possibly untrusted) project's tests inside an ephemeral,
    network-isolated Docker container. Two phases in the SAME container:
    1. install deps with network enabled (pip needs it)
    2. disconnect network, then execute pytest
    This avoids trusting arbitrary code with any network access during execution.
    """
    client = _client()
    ensure_sandbox_image(client)

    has_requirements = (source_dir / "requirements.txt").exists()

    container = client.containers.run(
        IMAGE_TAG,
        command="sleep 600",
        detach=True,
        volumes={str(source_dir): {"bind": "/workspace", "mode": "rw"}},
        working_dir="/workspace",
        user="runner",
        mem_limit=MEM_LIMIT,
        nano_cpus=NANO_CPUS,
        pids_limit=PIDS_LIMIT,
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        network_mode="bridge",
        remove=False,
    )

    try:
        install_log = "(tidak ada requirements.txt, skip install)"
        install_success = True
        if has_requirements:
            install_exit, install_output = container.exec_run(
                ["timeout", str(INSTALL_TIMEOUT_SECONDS), "pip", "install",
                 "--no-input", "--disable-pip-version-check", "-r", "requirements.txt"],
                user="runner",
                workdir="/workspace",
            )
            install_log = install_output.decode(errors="replace")
            install_success = install_exit == 0

        _disconnect_network(client, container)

        test_exit, test_output = container.exec_run(
            ["timeout", str(TEST_TIMEOUT_SECONDS), "python", "-m", "pytest", "-q",
             "--json-report", "--json-report-file=/tmp/.report.json", "generated_tests"],
            user="runner",
            workdir="/workspace",
        )
        raw_stdout = test_output.decode(errors="replace")
        timed_out = test_exit == TIMEOUT_KILLED_EXIT_CODE

        report_exit, report_output = container.exec_run(["cat", "/tmp/.report.json"], user="runner")
        report_raw = report_output.decode(errors="replace") if report_exit == 0 else ""

        summary, tests = _parse_pytest_json_report(report_raw)

        return ExecutionResult(
            install_success=install_success,
            install_log=install_log[-LOG_TAIL_CHARS:],
            timed_out=timed_out,
            summary=summary,
            tests=tests,
            raw_stdout=raw_stdout[-LOG_TAIL_CHARS:],
            raw_stderr="",
        )
    finally:
        try:
            container.stop(timeout=5)
        except Exception:
            pass
        try:
            container.remove(force=True)
        except Exception:
            pass
