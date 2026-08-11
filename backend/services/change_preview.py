import ast
import difflib
from pathlib import Path

from backend.services.file_reader import read_text_file
from backend.services.patch_applier import _is_duplicate_code
from backend.services.workspace_manager import WORKSPACE_ROOT


def validate_preview_workspace_path(project_path: str) -> Path:
    """
    Validate project path against SAGE WORKSPACE_ROOT for read-only preview.
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


def simulate_patch_in_memory(
    current_content: str, operation: str, anchor: str, code: str
) -> str:
    """
    Simulate a patch operation on current_content entirely in memory.
    Operations supported: insert, replace, delete, append.
    """
    if operation == "insert":
        if not anchor or anchor not in current_content:
            raise ValueError(
                "Insert operation requires an existing anchor in the file."
            )
        return current_content.replace(anchor, anchor + "\n" + code, 1)

    elif operation == "replace":
        if not anchor or anchor not in current_content:
            raise ValueError(
                "Replace operation requires an existing anchor in the file."
            )
        if current_content.count(anchor) != 1:
            raise ValueError(
                "Replace anchor must occur exactly once in the file."
            )
        return current_content.replace(anchor, code, 1)

    elif operation == "delete":
        if not anchor or anchor not in current_content:
            raise ValueError(
                "Delete operation requires an existing anchor in the file."
            )
        return current_content.replace(anchor, "", 1)

    elif operation == "append":
        if anchor != "":
            raise ValueError("Append operation must use an empty anchor.")
        return current_content.rstrip() + "\n\n" + code.strip() + "\n"

    else:
        raise ValueError(f"Unsupported operation: {operation}")


def validate_python_in_memory(code: str) -> dict:
    """
    Perform AST syntax validation on proposed Python code content in memory.
    """
    test_code = code.strip()
    try:
        ast.parse(test_code)
        return {"status": "passed", "valid": True, "error": ""}
    except SyntaxError as error:
        if test_code.startswith("@"):
            wrapped_code = (
                test_code
                + "\n"
                + "def __sage_validation_function__():\n"
                + "    pass\n"
            )
            try:
                ast.parse(wrapped_code)
                return {"status": "passed", "valid": True, "error": ""}
            except SyntaxError as err:
                return {
                    "status": "failed",
                    "valid": False,
                    "error": str(err),
                }

        return {
            "status": "failed",
            "valid": False,
            "error": str(error),
        }


def generate_file_preview(project_path: str, change_item: dict) -> dict:
    """
    Generate a read-only preview and unified diff for a single file change item.
    """
    root = validate_preview_workspace_path(project_path)

    file_path = change_item.get("file_path")
    operation = (change_item.get("operation") or "").strip().lower()
    anchor = change_item.get("anchor", "")
    code = change_item.get("code", "")
    reason = change_item.get("reason", "")

    if not file_path or not isinstance(file_path, str):
        return {
            "file_path": str(file_path),
            "operation": operation,
            "status": "invalid",
            "error": "Missing or invalid file_path.",
            "reason": reason,
            "diff": "",
            "content_before": "",
            "content_after": "",
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    target = (root / file_path).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return {
            "file_path": file_path,
            "operation": operation,
            "status": "invalid",
            "error": "Path is outside the project workspace.",
            "reason": reason,
            "diff": "",
            "content_before": "",
            "content_after": "",
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    if not target.exists():
        return {
            "file_path": file_path,
            "operation": operation,
            "status": "invalid",
            "error": f"File not found: {file_path}",
            "reason": reason,
            "diff": "",
            "content_before": "",
            "content_after": "",
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    if not target.is_file():
        return {
            "file_path": file_path,
            "operation": operation,
            "status": "invalid",
            "error": f"Path is not a file: {file_path}",
            "reason": reason,
            "diff": "",
            "content_before": "",
            "content_after": "",
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    try:
        current_content = read_text_file(target)
    except Exception as err:
        return {
            "file_path": file_path,
            "operation": operation,
            "status": "invalid",
            "error": f"Failed to read file: {err}",
            "reason": reason,
            "diff": "",
            "content_before": "",
            "content_after": "",
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    if (
        operation != "delete"
        and code
        and _is_duplicate_code(current_content, code)
    ):
        return {
            "file_path": file_path,
            "operation": operation,
            "status": "invalid",
            "error": "The proposed code already exists in the target file.",
            "reason": reason,
            "diff": "",
            "content_before": current_content,
            "content_after": current_content,
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    try:
        proposed_content = simulate_patch_in_memory(
            current_content=current_content,
            operation=operation,
            anchor=anchor,
            code=code,
        )
    except ValueError as val_err:
        return {
            "file_path": file_path,
            "operation": operation,
            "status": "invalid",
            "error": str(val_err),
            "reason": reason,
            "diff": "",
            "content_before": current_content,
            "content_after": current_content,
            "lines_added": 0,
            "lines_removed": 0,
            "syntax_verification": "not_available",
        }

    orig_lines = current_content.splitlines(keepends=True)
    new_lines = proposed_content.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )

    diff_text = "".join(diff_lines)

    lines_added = sum(
        1
        for line in diff_lines
        if line.startswith("+") and not line.startswith("+++")
    )
    lines_removed = sum(
        1
        for line in diff_lines
        if line.startswith("-") and not line.startswith("---")
    )

    if file_path.lower().endswith(".py"):
        syn_res = validate_python_in_memory(proposed_content)
        syntax_verification = syn_res["status"]
    else:
        syntax_verification = "not_available"

    return {
        "file_path": file_path,
        "operation": operation,
        "status": "valid",
        "reason": reason,
        "diff": diff_text,
        "content_before": current_content,
        "content_after": proposed_content,
        "lines_added": lines_added,
        "lines_removed": lines_removed,
        "syntax_verification": syntax_verification,
    }


def generate_change_preview(project_path: str, changes: list[dict]) -> dict:
    """
    Generate a read-only change preview for a complete multi-file change set.
    """
    root = validate_preview_workspace_path(project_path)

    if not isinstance(changes, list) or len(changes) == 0:
        return {
            "status": "failed",
            "message": "Change set must be a non-empty list of changes.",
            "files": [],
            "total_files": 0,
            "total_lines_added": 0,
            "total_lines_removed": 0,
        }

    seen_anchors = set()
    for idx, change in enumerate(changes):
        fp = change.get("file_path")
        op = change.get("operation")
        anc = change.get("anchor")
        if fp and op and op != "append":
            key = (fp, op, anc)
            if key in seen_anchors:
                return {
                    "status": "failed",
                    "message": (
                        f"Duplicate conflicting change targeting '{fp}' with"
                        f" operation '{op}'."
                    ),
                    "files": [],
                    "total_files": 0,
                    "total_lines_added": 0,
                    "total_lines_removed": 0,
                }
            seen_anchors.add(key)

    file_previews = []
    has_invalid = False
    total_added = 0
    total_removed = 0

    for change in changes:
        prev = generate_file_preview(str(root), change)
        file_previews.append(prev)
        if prev.get("status") != "valid":
            has_invalid = True
        else:
            total_added += prev.get("lines_added", 0)
            total_removed += prev.get("lines_removed", 0)

    if has_invalid:
        return {
            "status": "failed",
            "message": "Change preview validation failed.",
            "files": file_previews,
            "total_files": len(file_previews),
            "total_lines_added": total_added,
            "total_lines_removed": total_removed,
        }

    return {
        "status": "success",
        "message": "Change preview generated successfully.",
        "files": file_previews,
        "total_files": len(file_previews),
        "total_lines_added": total_added,
        "total_lines_removed": total_removed,
    }
