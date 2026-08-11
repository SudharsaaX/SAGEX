from pathlib import Path

from backend.services.backup_manager import create_backup
from backend.services.change_history import record_change
from backend.services.change_verifier import verify_changed_file
from backend.services.patch_applier import apply_patch, validate_patch
from backend.services.rollback_manager import rollback_change
from backend.services.test_runner import (
    run_project_tests,
    validate_workspace_path,
)


def validate_change_set(project_path: str, changes: list[dict]) -> Path:
    """
    Validate every patch in a multi-file change set before creating any backups
    or modifying any project files.
    """
    root = validate_workspace_path(project_path)

    if not isinstance(changes, list) or len(changes) == 0:
        raise ValueError("Change set must be a non-empty list of changes.")

    seen_anchors = set()

    for idx, change in enumerate(changes):
        if not isinstance(change, dict):
            raise ValueError(f"Change item at index {idx} must be a dictionary.")

        file_path = change.get("file_path")
        operation = change.get("operation")
        anchor = change.get("anchor")
        code = change.get("code")

        if not file_path or not isinstance(file_path, str):
            raise ValueError(f"Change item at index {idx} missing valid 'file_path'.")

        target_path = (root / file_path).resolve()
        try:
            target_path.relative_to(root)
        except ValueError:
            raise PermissionError(
                f"File path '{file_path}' attempts workspace traversal."
            )

        if not operation or operation not in {"insert", "replace", "append"}:
            raise ValueError(
                f"Change item '{file_path}' has unsupported operation: '{operation}'."
            )

        anchor_key = (file_path, operation, anchor)
        if anchor_key in seen_anchors and operation != "append":
            raise ValueError(
                f"Duplicate conflicting change targeting '{file_path}' with operation '{operation}'."
            )
        seen_anchors.add(anchor_key)

        try:
            validate_patch(
                project_path=str(root),
                file_path=file_path,
                operation=operation,
                anchor=anchor if anchor is not None else "",
                code=code if code is not None else "",
            )
        except (ValueError, FileNotFoundError, PermissionError, IsADirectoryError) as err:
            raise ValueError(
                f"Patch validation failed for '{file_path}': {err}"
            )


    return root


def create_backups_for_change_set(
    project_path: str, changes: list[dict]
) -> tuple[dict[str, str], list[str]]:
    """
    Create backups for every unique file affected by the change set.
    """
    unique_files = []
    for change in changes:
        fp = change["file_path"]
        if fp not in unique_files:
            unique_files.append(fp)

    backup_map = {}
    for file_path in unique_files:
        try:
            backup_path = create_backup(
                project_path=project_path, file_path=file_path
            )
            backup_map[file_path] = backup_path
        except Exception as error:
            raise RuntimeError(
                f"Failed to create backup for '{file_path}': {error}"
            )

    return backup_map, unique_files


def rollback_change_set(
    project_path: str, modified_files: list[str]
) -> dict:
    """
    Atomically restore all modified files using SAGE's rollback manager.
    """
    files_restored = []
    files_failed = []

    for file_path in modified_files:
        try:
            res = rollback_change(
                project_path=project_path, file_path=file_path
            )
            if res.get("status") == "rolled_back":
                files_restored.append(file_path)
            else:
                files_failed.append(file_path)
        except Exception:
            files_failed.append(file_path)

    status_str = "rolled_back" if len(files_failed) == 0 else "rollback_failed"

    return {
        "status": status_str,
        "files_restored": files_restored,
        "files_failed": files_failed,
    }


def run_change_transaction(
    project_path: str, changes: list[dict], run_tests: bool = False
) -> dict:
    """
    Execute a multi-file change set as an atomic transaction.
    If ANY validation, application, syntax verification, or test step fails,
    ALL modified files are rolled back immediately.
    """
    root = validate_change_set(project_path, changes)
    proj_str = str(root)

    backup_map, affected_files = create_backups_for_change_set(
        proj_str, changes
    )
    modified_files = []

    # Apply changes
    for change in changes:
        fp = change["file_path"]
        op = change["operation"]
        anc = change.get("anchor", "")
        code = change.get("code", "")

        app_res = apply_patch(
            project_path=proj_str,
            file_path=fp,
            operation=op,
            anchor=anc,
            code=code,
        )

        if fp not in modified_files:
            modified_files.append(fp)

        if app_res.get("status") != "success":
            rollback_res = rollback_change_set(proj_str, modified_files)
            hist = record_change(
                project_path=proj_str,
                file_path=", ".join(affected_files),
                operation="change_set",
                status="failed",
                verification_status="failed",
                rollback_status=rollback_res["status"],
                message=f"Patch application failed for '{fp}'. All changes rolled back.",
                files=affected_files,
            )
            return {
                "status": "failed",
                "message": f"Patch application failed for '{fp}'. All changes were rolled back.",
                "files": affected_files,
                "backups": list(backup_map.values()),
                "verification": {
                    "status": "failed",
                    "file_path": fp,
                    "message": app_res.get("message", "Application failed."),
                },
                "tests": {
                    "status": "skipped",
                    "reason": "Application failed before running tests.",
                },
                "rollback": rollback_res,
                "history": hist,
            }

    # Verify all modified files
    for fp in modified_files:
        ver_res = verify_changed_file(project_path=proj_str, file_path=fp)
        if ver_res.get("status") != "passed":
            rollback_res = rollback_change_set(proj_str, modified_files)
            hist = record_change(
                project_path=proj_str,
                file_path=", ".join(affected_files),
                operation="change_set",
                status="failed",
                verification_status="failed",
                rollback_status=rollback_res["status"],
                message=f"Syntax verification failed for '{fp}'. All changes rolled back.",
                files=affected_files,
            )
            return {
                "status": "failed",
                "message": f"Syntax verification failed for '{fp}'. The original files were restored.",
                "files": affected_files,
                "backups": list(backup_map.values()),
                "verification": ver_res,
                "tests": {
                    "status": "skipped",
                    "reason": "Syntax verification failed before running tests.",
                },
                "rollback": rollback_res,
                "history": hist,
            }

    # Automated project tests
    tests_res = {
        "status": "skipped",
        "reason": "Automated tests were not requested.",
    }

    if run_tests:
        tests_res = run_project_tests(project_path=proj_str)
        t_status = tests_res.get("status")

        if t_status in {"failed", "timeout"}:
            rollback_res = rollback_change_set(proj_str, modified_files)
            fail_msg = (
                "Project tests failed. The original files were restored."
                if t_status == "failed"
                else "Project tests timed out. The original files were restored."
            )
            hist = record_change(
                project_path=proj_str,
                file_path=", ".join(affected_files),
                operation="change_set",
                status="failed",
                verification_status=t_status,
                rollback_status=rollback_res["status"],
                message=fail_msg,
                files=affected_files,
            )
            return {
                "status": "failed",
                "message": fail_msg,
                "files": affected_files,
                "backups": list(backup_map.values()),
                "verification": {"status": "passed"},
                "tests": tests_res,
                "rollback": rollback_res,
                "history": hist,
            }

    t_status = tests_res.get("status")
    if t_status == "passed":
        ver_status = "passed"
        succ_msg = "Multi-file change set applied, verified, and project tests passed."
    elif t_status == "unsupported":
        ver_status = "unsupported"
        succ_msg = "Multi-file change set applied and verified, but project tests are unsupported."
    else:
        ver_status = "passed"
        succ_msg = "Multi-file change set applied and verified successfully."

    hist = record_change(
        project_path=proj_str,
        file_path=", ".join(affected_files),
        operation="change_set",
        status="success",
        verification_status=ver_status,
        rollback_status=None,
        message=succ_msg,
        files=affected_files,
    )

    return {
        "status": "success",
        "message": succ_msg,
        "files": affected_files,
        "backups": list(backup_map.values()),
        "verification": {"status": "passed"},
        "tests": tests_res,
        "history": hist,
    }
