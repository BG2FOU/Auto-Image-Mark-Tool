"""Exercise timeout/crash cleanup and both-stream command framing with a fake server."""

import subprocess
import sys
from pathlib import Path

import pytest

from aim_tool.services.exiftool import ExifTool, ExifToolError

SERVER = """
import sys, time
args = []
for line in sys.stdin:
    line = line.rstrip("\\r\\n")
    if line == "False" and args == ["-stay_open"]:
        break
    if not line.startswith("-execute"):
        args.append(line)
        continue
    if "-crash" in args:
        sys.exit(7)
    if "-slow" in args:
        time.sleep(5)
    status = 1 if "-failure" in args else 0
    if "-warn" in args:
        print("Warning: bad camera metadata", file=sys.stderr)
    marker = args[args.index("-echo4") + 1].replace("${status}", str(status))
    # Deliberately finish stderr first; the adapter must also await stdout.
    print(marker, file=sys.stderr, flush=True)
    time.sleep(0.005)
    print("payload", flush=True)
    print("{ready" + line[len("-execute"):] + "}", flush=True)
    args = []
"""


@pytest.fixture
def session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ExifTool:
    executable = tmp_path / "exiftool"
    executable.touch()
    monkeypatch.setattr(
        "aim_tool.services.exiftool.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess([], 0, "13.59\n", ""),
    )
    tool = ExifTool(executable, timeout=1, persistent=True)
    server = tmp_path / "server.py"
    server.write_text(SERVER)
    popen = subprocess.Popen
    monkeypatch.setattr(
        "aim_tool.services.exiftool.subprocess.Popen",
        lambda command, **kwargs: popen([sys.executable, str(server)], **kwargs),
    )
    yield tool
    tool.close()


def test_stderr_cannot_complete_request_before_stdout(session: ExifTool) -> None:
    assert session._run("-payload") == "payload\n"
    assert session._run("-payload") == "payload\n"


def test_warning_and_failure_are_not_carried_into_next_request(session: ExifTool) -> None:
    with pytest.raises(ExifToolError, match="metadata warning"):
        session._run("-warn", reject_warnings=True)
    assert session._run("-payload", reject_warnings=True) == "payload\n"
    with pytest.raises(ExifToolError, match="exited 1"):
        session._run("-failure")
    assert session._run("-payload") == "payload\n"


@pytest.mark.parametrize("argument", ("-slow", "-crash"))
def test_broken_session_is_cleaned_and_next_request_can_restart(
    session: ExifTool, argument: str
) -> None:
    session._run("-payload")
    process = session._process
    readers = tuple(session._readers)
    assert process is not None
    with pytest.raises(ExifToolError, match="session failed or timed out"):
        session._run(argument)
    assert process.poll() is not None
    assert not any(reader.is_alive() for reader in readers)
    assert session._process is None
    assert session._run("-payload") == "payload\n"


def test_rejects_multiline_arguments_without_starting_child(session: ExifTool) -> None:
    with pytest.raises(ExifToolError, match="newline"):
        session._run("-Artist=bad\n-execute99")
    assert session._process is None
