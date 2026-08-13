from pathlib import Path


IGNORED = {
    ".git",
    "venv",
    "node_modules",
    "__pycache__"
}


def search_project(workspace, query):
    results = []

    for path in workspace.root.rglob("*"):

        if not path.is_file():
            continue

        if any(part in IGNORED for part in path.parts):
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, PermissionError):
            continue

        if query.lower() in text.lower():
            results.append(str(path.relative_to(workspace.root)))

    return results