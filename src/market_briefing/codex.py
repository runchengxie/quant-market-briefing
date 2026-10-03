"""Noninteractive model execution with transactional output."""
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


def execute_stage(prompt: str, schema: Path, output: Path, model: str | None,
                  timeout_seconds: float, cwd: Path, *, command_prefix: list[str] | None = None) -> dict:
    if output.exists():
        raise FileExistsError(output)
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = output.parent / f".{output.name}.{uuid.uuid4().hex}.raw.json"
    command = [*(command_prefix or ["codex"]), "exec", "--ephemeral",
               "--sandbox", "read-only", "--ignore-user-config", "--json",
               "--skip-git-repo-check", "--output-schema", str(schema.resolve()),
               "--output-last-message", str(raw.resolve())]
    if model:
        command.extend(["--model", model])
    command.append("-")
    schema_data = json.loads(schema.read_text(encoding="utf-8"))
    try:
        for attempt in range(3):
            kwargs = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
            events_path = output.with_suffix(f".attempt-{attempt + 1}.events.jsonl")
            stderr_path = output.with_suffix(f".attempt-{attempt + 1}.stderr.log")
            with events_path.open("wb") as events, stderr_path.open("wb") as errors:
                process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                           stdout=events, stderr=errors, **kwargs)
                try:
                    process.communicate(prompt.encode("utf-8"), timeout=timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                       capture_output=True, check=False)
                    else:
                        os.killpg(process.pid, signal.SIGKILL)
                    process.kill()
                    process.wait()
                    raise TimeoutError("Codex stage exceeded timeout") from exc
            if process.returncode == 75 and attempt < 2:
                raw.unlink(missing_ok=True)
                time.sleep(0.2 * (attempt + 1))
                continue
            if process.returncode:
                raise RuntimeError(f"Codex stage failed with exit code {process.returncode}; see {stderr_path}")
            break
        if not raw.is_file():
            raise ValueError("Codex produced no final output")
        try:
            payload = json.loads(raw.read_text(encoding="utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid final JSON") from exc
        errors = list(Draft202012Validator(schema_data, format_checker=FormatChecker()).iter_errors(payload))
        if errors:
            raise ValueError(f"Invalid final schema: {errors[0].message}")
        raw.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n",
                       encoding="utf-8")
        os.link(raw, output)
        return payload
    finally:
        raw.unlink(missing_ok=True)
