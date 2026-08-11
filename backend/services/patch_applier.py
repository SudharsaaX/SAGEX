from pathlib import Path

from backend.services.file_reader import (
    read_text_file,
)


def _is_duplicate_code(
    current_content: str,
    code: str,
) -> bool:
    """
    Check whether the proposed code already exists
    as a complete code block in the target file.

    This avoids treating a short fragment such as
    'VALUE =' as a duplicate of:

        VALUE = "something"

    The duplicate check is based on complete lines
    rather than arbitrary substrings.
    """

    normalized_code = code.strip()

    if not normalized_code:
        return False

    current_lines = (
        current_content
        .splitlines()
    )

    code_lines = (
        normalized_code
        .splitlines()
    )

    # -----------------------------------------
    # Single-line code
    # -----------------------------------------

    if len(code_lines) == 1:

        proposed_line = (
            code_lines[0].strip()
        )

        for current_line in current_lines:

            if (
                current_line.strip()
                == proposed_line
            ):
                return True

        return False

    # -----------------------------------------
    # Multi-line code
    # -----------------------------------------

    normalized_proposed_lines = [
        line.strip()
        for line in code_lines
    ]

    proposed_length = len(
        normalized_proposed_lines
    )

    for index in range(
        len(current_lines)
        - proposed_length
        + 1
    ):

        current_block = [
            line.strip()
            for line in current_lines[
                index:
                index + proposed_length
            ]
        ]

        if (
            current_block
            == normalized_proposed_lines
        ):
            return True

    return False


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

    if _is_duplicate_code(
        current_content,
        code,
    ):

        raise ValueError(
            "The proposed code already "
            "exists in the target file. "
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

        new_content = (
            current_content.replace(
                anchor,
                anchor + "\n" + code,
                1,
            )
        )

    elif operation == "replace":

        new_content = (
            current_content.replace(
                anchor,
                code,
                1,
            )
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