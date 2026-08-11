import json
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
        raise FileNotFoundError(
            f"Project path does not exist: {root}"
        )

    if not root.is_dir():
        raise NotADirectoryError(
            f"Project path is not a directory: {root}"
        )

    files = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        relative_path = path.relative_to(root)

        if any(
            part in IGNORED_DIRECTORIES
            for part in relative_path.parts
        ):
            continue

        files.append(str(relative_path))

    files.sort()

    project_info = detect_project_info(root)
    important_files = identify_important_files(files)

    return {
        "project_path": str(root),
        "total_files": len(files),
        "files": files,
        "project_info": project_info,
        "important_files": important_files,
    }


def identify_important_files(files: list[str]) -> dict:
    important = {
        "entry_points": [],
        "configuration": [],
        "documentation": [],
        "api_files": [],
        "service_files": [],
    }

    for file in files:
        path = Path(file)
        name = path.name.lower()
        parts = {part.lower() for part in path.parts}

        if name in {
            "main.py",
            "app.py",
            "server.py",
            "index.js",
            "index.jsx",
            "index.ts",
            "index.tsx",
        }:
            important["entry_points"].append(file)

        if name in {
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "package-lock.json",
            "vite.config.js",
            "vite.config.ts",
            "dockerfile",
            ".env.example",
        }:
            important["configuration"].append(file)

        if name in {
            "readme.md",
            "readme.txt",
        }:
            important["documentation"].append(file)

        if (
            "api" in parts
            or "routes" in parts
            or "routers" in parts
            or name in {
                "main.py",
                "server.py",
                "api.py",
            }
        ):
            important["api_files"].append(file)

        if (
            "services" in parts
            or "service" in parts
        ):
            important["service_files"].append(file)

    return important


def detect_project_info(root: Path) -> dict:
    package_json_path = root / "package.json"

    if package_json_path.exists():
        return detect_javascript_project(
            root,
            package_json_path,
        )

    return detect_python_project(root)


def detect_javascript_project(
    root: Path,
    package_json_path: Path,
) -> dict:
    try:
        package_text = read_text_file(
            package_json_path
        )

        package_data = json.loads(package_text)

    except (
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
    ):
        return {
            "language": "JavaScript",
            "package_manager": detect_package_manager(root),
            "framework": None,
            "package_file": "package.json",
        }

    dependencies = {
        **package_data.get("dependencies", {}),
        **package_data.get("devDependencies", {}),
    }

    framework = detect_javascript_framework(
        dependencies
    )

    return {
        "language": "JavaScript",
        "package_manager": detect_package_manager(root),
        "framework": framework,
        "package_file": "package.json",
    }


def detect_python_project(root: Path) -> dict:
    requirements_path = root / "requirements.txt"
    pyproject_path = root / "pyproject.toml"

    if (
        not requirements_path.exists()
        and not pyproject_path.exists()
    ):
        return {
            "language": None,
            "package_manager": None,
            "framework": None,
            "package_file": None,
        }

    dependencies_text = ""

    if requirements_path.exists():
        try:
            dependencies_text = read_text_file(
                requirements_path
            ).lower()

        except (
            OSError,
            UnicodeDecodeError,
        ):
            dependencies_text = ""

    if pyproject_path.exists():
        try:
            dependencies_text += (
                "\n"
                + read_text_file(
                    pyproject_path
                ).lower()
            )

        except (
            OSError,
            UnicodeDecodeError,
        ):
            pass

    framework = detect_python_framework(
        dependencies_text
    )

    package_file = None

    if pyproject_path.exists():
        package_file = "pyproject.toml"

    elif requirements_path.exists():
        package_file = "requirements.txt"

    return {
        "language": "Python",
        "package_manager": "pip",
        "framework": framework,
        "package_file": package_file,
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


def detect_package_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"

    if (root / "yarn.lock").exists():
        return "yarn"

    if (root / "package-lock.json").exists():
        return "npm"

    return "npm"


def detect_javascript_framework(
    dependencies: dict,
) -> str | None:

    if "next" in dependencies:
        return "Next.js"

    if "react" in dependencies:
        return "React"

    if "vue" in dependencies:
        return "Vue"

    if (
        "angular" in dependencies
        or "@angular/core" in dependencies
    ):
        return "Angular"

    if "svelte" in dependencies:
        return "Svelte"

    return None


def detect_python_framework(
    dependencies_text: str,
) -> str | None:

    if "fastapi" in dependencies_text:
        return "FastAPI"

    if "django" in dependencies_text:
        return "Django"

    if "flask" in dependencies_text:
        return "Flask"

    return None