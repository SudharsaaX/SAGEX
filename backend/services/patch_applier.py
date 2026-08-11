from pathlib import Path

from backend.services.file_reader import (
    read_text_file,
)


def validate_patch(
    project_path: str,
    file_path: str,
    operation: str,
    anchor: str,
    code: str,
) -> dict:
    """
    Validate a patch without modifying the target file.

    Returns the current file content and the
    validated target path.
    """

    root = Path(
        project_path
    ).resolve()

    target = (
        root / file_path
    ).resolve()

    # -----------------------------------------
    # Security: prevent path traversal
    # -----------------------------------------

    try:
        target.relative_to(root)

    except ValueError:
        raise PermissionError(
            "The requested file is outside "
            "the project directory."
        )

    # -----------------------------------------
    # File validation
    # -----------------------------------------

    if not target.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    if not target.is_file():
        raise IsADirectoryError(
            f"Path is not a file: {file_path}"
        )

    current_content = read_text_file(
        target
    )

    # -----------------------------------------
    # Operation validation
    # -----------------------------------------

    if operation not in {
        "insert",
        "replace",
        "append",
    }:
        raise ValueError(
            f"Unsupported operation: {operation}"
        )

    # -----------------------------------------
    # Duplicate protection
    # -----------------------------------------

    normalized_code = code.strip()

    if normalized_code and (
        normalized_code in current_content
    ):
        raise ValueError(
            "The proposed code already exists "
            "in the target file. "
            "Patch rejected to prevent "
            "duplicate code."
        )

    # -----------------------------------------
    # Anchor validation
    # -----------------------------------------

    if operation in {
        "insert",
        "replace",
    }:

        if not anchor:
            raise ValueError(
                f"{operation.capitalize()} "
                "operation requires an anchor."
            )

        if anchor not in current_content:
            raise ValueError(
                "The specified anchor was not "
                "found in the file."
            )

    # -----------------------------------------
    # Validation successful
    # -----------------------------------------

    return {
        "target": target,
        "current_content": current_content,
    }


def apply_patch(
    project_path: str,
    file_path: str,
    operation: str,
    anchor: str,
    code: str,
) -> dict:
    """
    Validate and apply a patch to a project file.

    The target file is modified only after
    all validation checks have passed.
    """

    validation = validate_patch(
        project_path=project_path,
        file_path=file_path,
        operation=operation,
        anchor=anchor,
        code=code,
    )

    target = validation[
        "target"
    ]

    current_content = validation[
        "current_content"
    ]

    # -----------------------------------------
    # Build new content
    # -----------------------------------------

    if operation == "insert":

        new_content = current_content.replace(
            anchor,
            anchor + "\n" + code,
            1,
        )

    elif operation == "replace":

        new_content = current_content.replace(
            anchor,
            code,
            1,
        )

    else:
        # append

        new_content = (
            current_content.rstrip()
            + "\n\n"
            + code.strip()
            + "\n"
        )

    # -----------------------------------------
    # Safety check
    # -----------------------------------------

    if new_content == current_content:

        raise ValueError(
            "The proposed patch would not "
            "change the file."
        )

    # -----------------------------------------
    # Write modified content
    # -----------------------------------------

    target.write_text(
        new_content,
        encoding="utf-8",
    )

    # -----------------------------------------
    # Return result
    # -----------------------------------------

    return {
        "status": "success",
        "file_path": file_path,
        "operation": operation,
        "message": (
            "Patch applied successfully."
        ),
        "content_before": current_content,
        "content_after": new_content,
    }