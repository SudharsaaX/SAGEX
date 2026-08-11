from pathlib import Path


def apply_patch(
    project_path: str,
    file_path: str,
    operation: str,
    anchor: str,
    code: str,
) -> dict:
    """
    Apply a validated code patch to a project file.

    The patch is only applied when:
    - The target file exists.
    - The target file is inside the project.
    - The requested operation is supported.
    - The anchor exists when required.
    - The code is not already present.
    """

    root = Path(project_path).resolve()
    target = (root / file_path).resolve()

    # Security: prevent path traversal

    try:
        target.relative_to(root)

    except ValueError:
        raise PermissionError(
            "The requested file is outside "
            "the project directory."
        )

    # File validation

    if not target.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    if not target.is_file():
        raise IsADirectoryError(
            f"Path is not a file: {file_path}"
        )

    # Read existing content

    current_content = read_text_file(target)

    # Validate operation

    if operation not in {
        "insert",
        "replace",
        "append",
    }:
        raise ValueError(
            f"Unsupported operation: {operation}"
        )

    # Prevent duplicate code

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

    # Insert operation

    if operation == "insert":

        if not anchor:
            raise ValueError(
                "Insert operation requires "
                "an anchor."
            )

        if anchor not in current_content:
            raise ValueError(
                "The specified anchor was not "
                "found in the file."
            )

        new_content = current_content.replace(
            anchor,
            anchor + "\n" + code,
            1,
        )

    # Replace operation

    elif operation == "replace":

        if not anchor:
            raise ValueError(
                "Replace operation requires "
                "an anchor."
            )

        if anchor not in current_content:
            raise ValueError(
                "The specified anchor was not "
                "found in the file."
            )

        new_content = current_content.replace(
            anchor,
            code,
            1,
        )

    # Append operation

    else:

        new_content = (
            current_content.rstrip()
            + "\n\n"
            + code.strip()
            + "\n"
        )

    # Write modified content

    target.write_text(
        new_content,
        encoding="utf-8",
    )

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


def read_text_file(
    path: Path,
) -> str:
    """
    Read a text file using common encodings.
    """

    encodings = [
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
        "cp1252",
        "latin-1",
    ]

    last_error = None

    for encoding in encodings:

        try:
            return path.read_text(
                encoding=encoding
            )

        except UnicodeDecodeError as error:
            last_error = error

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        (
            "Could not decode file using "
            "supported encodings."
        ),
    ) from last_error