import ast
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import threading

from backend.services.file_reader import read_text_file
from backend.services.project_analyzer import scan_project
from backend.services.workspace_manager import WORKSPACE_ROOT


# =========================================================
# PROCESS REGISTRY & LOG STORAGE
# =========================================================

_running_processes: dict[str, dict] = {}
_logs_history: dict[str, dict] = {}
_registry_lock = threading.Lock()


# =========================================================
# WORKSPACE SECURITY HELPERS
# =========================================================


def validate_workspace_path(project_path: str) -> Path:
    """
    Validate that project_path exists, is a directory,
    and resides inside SAGE's allowed workspace root.
    """
    root = Path(project_path).resolve()

    try:
        root.relative_to(WORKSPACE_ROOT.resolve())
    except ValueError:
        raise PermissionError(
            "Project path is outside SAGE workspace directory."
        )

    if not root.exists():
        raise FileNotFoundError(
            f"Project workspace path does not exist: {root}"
        )

    if not root.is_dir():
        raise NotADirectoryError(
            f"Project workspace path is not a directory: {root}"
        )

    return root


# =========================================================
# COMMAND INFERENCE
# =========================================================


def _detect_fastapi_app_target(
    project_path: Path, py_files: list[str]
) -> str | None:
    """
    Inspect Python entry point candidate files to find a valid FastAPI app instance.
    Returns module import string e.g. "main:app" or "src.app:app".
    """
    candidates = []

    for file_rel in py_files:
        file_abs = (project_path / file_rel).resolve()
        if not file_abs.exists() or not file_abs.is_file():
            continue

        try:
            content = read_text_file(file_abs)
            parsed = ast.parse(content)
        except Exception:
            continue

        has_fastapi_instance = False
        app_var_name = "app"

        for node in ast.walk(parsed):
            if isinstance(node, ast.Assign):
                if isinstance(node.value, ast.Call):
                    func = node.value.func
                    func_name = None
                    if isinstance(func, ast.Name):
                        func_name = func.id
                    elif isinstance(func, ast.Attribute):
                        func_name = func.attr

                    if func_name == "FastAPI":
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                app_var_name = target.id
                                has_fastapi_instance = True
                                break

        if has_fastapi_instance:
            mod_parts = list(Path(file_rel).with_suffix("").parts)
            mod_path = ".".join(mod_parts)
            candidates.append(f"{mod_path}:{app_var_name}")

    if len(candidates) == 1:
        return candidates[0]

    return None


def infer_start_command(project_path: str) -> dict:
    """
    Inspect an uploaded SAGE project and safely infer its start command.
    Does NOT execute shell=True or guess arbitrarily.
    """
    root = validate_workspace_path(project_path)
    analysis = scan_project(str(root))

    project_info = analysis.get("project_info", {})
    important_files = analysis.get("important_files", {})
    entry_points = important_files.get("entry_points", [])

    framework = project_info.get("framework")
    language = project_info.get("language")
    package_file = project_info.get("package_file")

    # 1. FastAPI Detection
    if framework == "FastAPI":
        py_candidates = [
            f for f in entry_points if f.lower().endswith(".py")
        ]
        if not py_candidates:
            py_candidates = [
                f
                for f in analysis.get("files", [])
                if f.lower().endswith(".py")
            ]

        target = _detect_fastapi_app_target(root, py_candidates)
        if target:
            return {
                "status": "success",
                "command": ["uvicorn", target],
                "command_type": "fastapi",
                "reason": f"Detected FastAPI application target: {target}",
            }
        else:
            return {
                "status": "failed",
                "command": None,
                "command_type": None,
                "reason": (
                    "Detected FastAPI framework, but could not safely "
                    "determine a unique FastAPI application target."
                ),
            }

    # 2. General Python Detection
    py_entrypoints = [
        f for f in entry_points if f.lower().endswith(".py")
    ]
    if not py_entrypoints and language == "Python":
        all_files = analysis.get("files", [])
        py_entrypoints = [
            f
            for f in all_files
            if Path(f).name.lower() in {"main.py", "app.py"}
        ]

    if py_entrypoints:
        main_apps = [
            f
            for f in py_entrypoints
            if Path(f).name.lower() in {"main.py", "app.py"}
        ]
        if len(main_apps) == 1:
            chosen = main_apps[0]
            return {
                "status": "success",
                "command": ["python", chosen],
                "command_type": "python",
                "reason": f"Found Python entry point: {chosen}",
            }
        elif len(py_entrypoints) == 1:
            chosen = py_entrypoints[0]
            return {
                "status": "success",
                "command": ["python", chosen],
                "command_type": "python",
                "reason": f"Found Python entry point: {chosen}",
            }
        else:
            return {
                "status": "failed",
                "command": None,
                "command_type": None,
                "reason": (
                    "Multiple potential Python entry points found "
                    f"({main_apps or py_entrypoints}); unable to determine primary entry point safely."
                ),
            }

    # 3. Node/npm Detection
    if package_file == "package.json" or (root / "package.json").exists():
        pkg_path = root / "package.json"
        if pkg_path.exists():
            try:
                pkg_text = read_text_file(pkg_path)
                pkg_data = json.loads(pkg_text)
                scripts = pkg_data.get("scripts", {})
                if (
                    isinstance(scripts, dict)
                    and "start" in scripts
                    and str(scripts["start"]).strip()
                ):
                    return {
                        "status": "success",
                        "command": ["npm", "start"],
                        "command_type": "node",
                        "reason": "Found 'start' script in package.json",
                    }
                else:
                    return {
                        "status": "failed",
                        "command": None,
                        "command_type": None,
                        "reason": (
                            "package.json exists but does not contain a valid"
                            " 'start' script."
                        ),
                    }
            except Exception as e:
                return {
                    "status": "failed",
                    "command": None,
                    "command_type": None,
                    "reason": f"Failed to parse package.json: {e}",
                }

    # 4. Unknown / Unsupported Project
    return {
        "status": "failed",
        "command": None,
        "command_type": None,
        "reason": "Could not safely determine a project start command.",
    }


# =========================================================
# BACKGROUND STREAM READERS
# =========================================================


def _stream_reader(stream, storage_list: list):
    """Continuously read lines from a stream to prevent pipe blocking."""
    try:
        for line in iter(stream.readline, ""):
            storage_list.append(line)
    except Exception:
        pass
    finally:
        try:
            stream.close()
        except Exception:
            pass


# =========================================================
# PROCESS STARTING & MANAGEMENT
# =========================================================


def start_project(
    project_path: str,
    command: list[str] | None = None,
) -> dict:
    """
    Start a project process using subprocess.Popen (shell=False).
    Prevents starting duplicate processes for the same workspace.
    """
    root = validate_workspace_path(project_path)
    workspace_key = str(root)

    with _registry_lock:
        if workspace_key in _running_processes:
            entry = _running_processes[workspace_key]
            proc = entry["process"]
            if proc.poll() is None:
                return {
                    "status": "already_running",
                    "pid": entry["pid"],
                    "project_path": workspace_key,
                    "command": entry["command"],
                    "message": "Project process is already running.",
                }
            else:
                _logs_history[workspace_key] = {
                    "stdout": "".join(entry["stdout_list"]),
                    "stderr": "".join(entry["stderr_list"]),
                    "exit_code": proc.poll(),
                }
                del _running_processes[workspace_key]

        if command is None:
            inference = infer_start_command(str(root))
            if inference["status"] != "success":
                return {
                    "status": "failed",
                    "reason": inference["reason"],
                    "project_path": workspace_key,
                }
            command = inference["command"]

        if not isinstance(command, list) or not command:
            return {
                "status": "failed",
                "reason": (
                    "Command must be a non-empty list of string arguments."
                ),
                "project_path": workspace_key,
            }

        executable_arg = command[0]
        executable_path = shutil.which(executable_arg) or executable_arg

        cmd_list = [executable_path] + command[1:]

        try:
            proc = subprocess.Popen(
                cmd_list,
                cwd=str(root),
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as error:
            return {
                "status": "failed",
                "reason": f"Failed to start process: {error}",
                "project_path": workspace_key,
            }

        stdout_list = []
        stderr_list = []

        t_out = threading.Thread(
            target=_stream_reader,
            args=(proc.stdout, stdout_list),
            daemon=True,
        )
        t_err = threading.Thread(
            target=_stream_reader,
            args=(proc.stderr, stderr_list),
            daemon=True,
        )

        t_out.start()
        t_err.start()

        _running_processes[workspace_key] = {
            "process": proc,
            "pid": proc.pid,
            "command": command,
            "project_path": workspace_key,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "stdout_list": stdout_list,
            "stderr_list": stderr_list,
            "threads": [t_out, t_err],
            "stopped_by_sage": False,
        }

        return {
            "status": "started",
            "pid": proc.pid,
            "command": command,
            "project_path": workspace_key,
        }


# =========================================================
# PROCESS STATUS
# =========================================================


def get_project_status(project_path: str) -> dict:
    """
    Get the status of a project process (running, stopped, failed).
    """
    root = validate_workspace_path(project_path)
    workspace_key = str(root)

    with _registry_lock:
        if workspace_key not in _running_processes:
            if workspace_key in _logs_history:
                log_entry = _logs_history[workspace_key]
                if log_entry.get("stopped_by_sage"):
                    status_str = "stopped"
                else:
                    exit_code = log_entry.get("exit_code", 0)
                    status_str = "stopped" if exit_code == 0 else "failed"

                return {
                    "status": status_str,
                    "pid": None,
                    "exit_code": log_entry.get("exit_code"),
                    "project_path": workspace_key,
                }

            return {
                "status": "stopped",
                "pid": None,
                "exit_code": None,
                "project_path": workspace_key,
            }

        entry = _running_processes[workspace_key]
        proc = entry["process"]
        poll_res = proc.poll()

        if poll_res is None:
            return {
                "status": "running",
                "pid": entry["pid"],
                "command": entry["command"],
                "project_path": workspace_key,
            }

        exit_code = poll_res
        stopped_by_sage = entry.get("stopped_by_sage", False)
        if stopped_by_sage:
            status_str = "stopped"
        else:
            status_str = "stopped" if exit_code == 0 else "failed"

        _logs_history[workspace_key] = {
            "stdout": "".join(entry["stdout_list"]),
            "stderr": "".join(entry["stderr_list"]),
            "exit_code": exit_code,
            "stopped_by_sage": stopped_by_sage,
        }
        del _running_processes[workspace_key]

        return {
            "status": status_str,
            "pid": entry["pid"],
            "exit_code": exit_code,
            "command": entry["command"],
            "project_path": workspace_key,
        }


# =========================================================
# STOP PROCESS
# =========================================================


def stop_project(project_path: str) -> dict:
    """
    Stop a SAGE-registered project process cleanly.
    Tries terminate() first, then kill() if timeout occurs.
    """
    root = validate_workspace_path(project_path)
    workspace_key = str(root)

    with _registry_lock:
        if workspace_key not in _running_processes:
            return {
                "status": "already_stopped",
                "project_path": workspace_key,
                "message": "Project process is not running.",
            }

        entry = _running_processes[workspace_key]
        proc = entry["process"]

        if proc.poll() is not None:
            exit_code = proc.poll()
            stopped_by_sage = entry.get("stopped_by_sage", False)
            _logs_history[workspace_key] = {
                "stdout": "".join(entry["stdout_list"]),
                "stderr": "".join(entry["stderr_list"]),
                "exit_code": exit_code,
                "stopped_by_sage": stopped_by_sage,
            }
            del _running_processes[workspace_key]
            return {
                "status": "already_stopped",
                "project_path": workspace_key,
                "message": "Project process has already exited.",
            }

        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass

        exit_code = proc.poll()

        _logs_history[workspace_key] = {
            "stdout": "".join(entry["stdout_list"]),
            "stderr": "".join(entry["stderr_list"]),
            "exit_code": exit_code,
            "stopped_by_sage": True,
        }
        del _running_processes[workspace_key]

        return {
            "status": "stopped",
            "pid": entry["pid"],
            "project_path": workspace_key,
            "message": "Project process stopped successfully.",
        }


# =========================================================
# GET LOGS
# =========================================================


def get_project_logs(project_path: str) -> dict:
    """
    Retrieve captured stdout and stderr for a project process.
    """
    root = validate_workspace_path(project_path)
    workspace_key = str(root)

    with _registry_lock:
        if workspace_key in _running_processes:
            entry = _running_processes[workspace_key]
            return {
                "status": "success",
                "project_path": workspace_key,
                "stdout": "".join(entry["stdout_list"]),
                "stderr": "".join(entry["stderr_list"]),
            }

        if workspace_key in _logs_history:
            history_entry = _logs_history[workspace_key]
            return {
                "status": "success",
                "project_path": workspace_key,
                "stdout": history_entry["stdout"],
                "stderr": history_entry["stderr"],
            }

        return {
            "status": "success",
            "project_path": workspace_key,
            "stdout": "",
            "stderr": "",
            "message": "No execution logs found for this project.",
        }
