from project_tools.workspace import Workspace


def read_file(workspace, file_path):
    path = workspace.get_path(file_path)

    if not path.exists():
        return "File not found."

    if not path.is_file():
        return "Not a file."

    return path.read_text(encoding="utf-8")