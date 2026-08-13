def write_file(workspace, file_path, content):
    path = workspace.get_path(file_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

    return f"File written: {file_path}"