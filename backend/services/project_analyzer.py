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


def scan_project(project_path: str) -> dict:
    root = Path(project_path).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Project path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Project path is not a directory: {root}")

    files = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative_path = path.relative_to(root)

        if any(part in IGNORED_DIRECTORIES for part in relative_path.parts):
            continue

        files.append(str(relative_path))

    files.sort()

    return {
        "project_path": str(root),
        "total_files": len(files),
        "files": files,
    }