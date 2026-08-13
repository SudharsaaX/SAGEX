from pathlib import Path


class Workspace:

    def __init__(self, project_path):
        self.root = Path(project_path).resolve()

    def get_path(self, file_path):
        path = (self.root / file_path).resolve()

        if not path.is_relative_to(self.root):
            raise PermissionError("Access outside project is not allowed.")

        return path