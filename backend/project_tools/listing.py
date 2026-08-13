def list_files(workspace):
    files = []

    ignored = {
        "venv",
        ".git",
        "__pycache__",
        "node_modules",
        ".sage-x",
        ".env"
    }

    for path in workspace.root.rglob("*"):
        if path.is_file():
            relative_path = path.relative_to(workspace.root)

            # Ignore unwanted directories
            if any(part in ignored for part in relative_path.parts):
                continue

            files.append(str(relative_path))

    return files