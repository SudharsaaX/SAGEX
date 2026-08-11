from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".next",
    "dist",
    "build",
}


def read_project_file(
    project_path: str,
    file_path: str,
) -> dict:

    root = Path(project_path).resolve()

    requested_file = Path(file_path)

    if requested_file.is_absolute():
        target = requested_file.resolve()

    else:
        target = (
            root / requested_file
        ).resolve()

    try:
        target.relative_to(root)

    except ValueError:
        raise PermissionError(
            "The requested file is outside "
            "the project directory."
        )

    if any(
        part in IGNORED_DIRECTORIES
        for part in target.relative_to(root).parts
    ):
        raise PermissionError(
            "Access to this project directory "
            "is not allowed."
        )

    if not target.exists():
        raise FileNotFoundError(
            f"File does not exist: {file_path}"
        )

    if not target.is_file():
        raise IsADirectoryError(
            f"Path is not a file: {file_path}"
        )

    content = read_text_file(target)

    return {
        "file_path": str(
            target.relative_to(root)
        ),
        "size": len(content),
        "content": content,
    }


def read_text_file(path: Path) -> str:
    encodings = [
        "utf-8",
        "utf-8-sig",
        "utf-16",
        "utf-16-le",
        "utf-16-be",
    ]

    for encoding in encodings:
        try:
            return path.read_text(
                encoding=encoding
            )

        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError(
        "unknown",
        b"",
        0,
        1,
        f"Unable to decode text file: {path}",
    )