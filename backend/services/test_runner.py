import json
from pathlib import Path
import shutil
import subprocess
import time

from backend.services.file_reader import read_text_file
from backend.services.project_analyzer import scan_project
from backend.services.workspace_manager import WORKSPACE_ROOT

DEFAULT_TIMEOUT_SECONDS = 300


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
# TEST COMMAND INFERENCE
# =========================================================


def _has_python_test_evidence(root: Path, files: list[str]) -> bool:
    """
    Check if a Python project contains test directories or test files.
    """
    if (root / "tests").exists() or (root / "test").exists():
        return True

    for file_path_str in files:
        p = Path(file_path_str)
        name = p.name.lower()
        parts = [part.lower() for part in p.parts]

        if "tests" in parts or "test" in parts:
            return True

        if name.startswith("test_") and name.endswith(".py"):
            return True

        if name.endswith("_test.py"):
            return True

    return False


def infer_test_command(project_path: str) -> dict:
    """
    Inspect an uploaded SAGE project and safely infer its test command.
    Only infers pytest or npm test when evidence of tests exists.
    """
    root = validate_workspace_path(project_path)
    analysis = scan_project(str(root))

    project_info = analysis.get("project_info", {})
    all_files = analysis.get("files", [])

    language = project_info.get("language")
    package_file = project_info.get("package_file")

    has_py_tests = _has_python_test_evidence(root, all_files)

    has_node_tests = False
    if package_file == "package.json" or (root / "package.json").exists():
        pkg_path = root / "package.json"
        if pkg_path.exists():
            try:
                pkg_text = read_text_file(pkg_path)
                pkg_data = json.loads(pkg_text)
                scripts = pkg_data.get("scripts", {})
                if (
                    isinstance(scripts, dict)
                    and "test" in scripts
                    and str(scripts["test"]).strip()
                ):
                    has_node_tests = True
            except Exception:
                pass

    # Handle language priority and ambiguity
    if has_py_tests and has_node_tests:
        if language == "Python":
            return {
                "status": "success",
                "command": ["pytest"],
                "framework": "pytest",
                "reason": "Detected Python project with pytest test files.",
            }
        elif language == "JavaScript":
            return {
                "status": "success",
                "command": ["npm", "test"],
                "framework": "npm_test",
                "reason": "Detected Node.js project with 'test' script in package.json.",
            }
        else:
            return {
                "status": "unsupported",
                "command": None,
                "framework": None,
                "reason": (
                    "Multiple potential test frameworks detected, but primary"
                    " language is ambiguous."
                ),
            }

    if has_py_tests:
        return {
            "status": "success",
            "command": ["pytest"],
            "framework": "pytest",
            "reason": "Detected Python project with pytest test files.",
        }

    if has_node_tests:
        return {
            "status": "success",
            "command": ["npm", "test"],
            "framework": "npm_test",
            "reason": (
                "Detected Node.js project with 'test' script in package.json."
            ),
        }

    return {
        "status": "unsupported",
        "command": None,
        "framework": None,
        "reason": "No supported test framework or test files were detected.",
    }


# =========================================================
# RUN PROJECT TESTS
# =========================================================


def run_project_tests(
    project_path: str, timeout_seconds: int | None = None
) -> dict:
    """
    Safely execute automated tests for an uploaded SAGE project using Popen.
    Enforces workspace validation, timeout, and output capture.
    """
    if timeout_seconds is None:
        timeout_seconds = DEFAULT_TIMEOUT_SECONDS

    if not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be a positive integer.")

    timeout_val = min(int(timeout_seconds), 600)

    root = validate_workspace_path(project_path)

    inference = infer_test_command(str(root))
    if inference["status"] != "success":
        return inference

    command = inference["command"]
    framework = inference["framework"]

    executable_arg = command[0]
    executable_path = shutil.which(executable_arg) or executable_arg

    cmd_list = [executable_path] + command[1:]

    start_time = time.time()

    try:
        proc = subprocess.Popen(
            cmd_list,
            cwd=str(root),
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = proc.communicate(timeout=timeout_val)
        duration = round(time.time() - start_time, 2)
        exit_code = proc.poll()

        status_str = "passed" if exit_code == 0 else "failed"

        return {
            "status": status_str,
            "command": command,
            "framework": framework,
            "exit_code": exit_code,
            "stdout": stdout or "",
            "stderr": stderr or "",
            "duration_seconds": duration,
        }

    except subprocess.TimeoutExpired:
        try:
            proc.terminate()
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            proc.kill()
            stdout, stderr = proc.communicate()

        duration = round(time.time() - start_time, 2)

        return {
            "status": "timeout",
            "command": command,
            "framework": framework,
            "exit_code": proc.poll(),
            "stdout": stdout or "",
            "stderr": stderr or "",
            "duration_seconds": duration,
            "reason": (
                f"Test execution exceeded timeout limit of {timeout_val}"
                " seconds."
            ),
        }

    except Exception as error:
        duration = round(time.time() - start_time, 2)
        return {
            "status": "failed",
            "command": command,
            "framework": framework,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Subprocess execution error: {error}",
            "duration_seconds": duration,
        }
