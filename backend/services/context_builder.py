from backend.services.file_reader import (
    read_project_file,
)
from backend.services.project_analyzer import (
    scan_project,
)


MAX_FILE_CHARS = 12000
MAX_TOTAL_CHARS = 30000


def build_project_context(
    project_path: str,
) -> dict:

    project = scan_project(
        project_path
    )

    important_files = project[
        "important_files"
    ]

    selected_files = select_context_files(
        important_files
    )

    file_contexts = []
    total_chars = 0

    for file_path in selected_files:

        if total_chars >= MAX_TOTAL_CHARS:
            break

        try:
            file_data = read_project_file(
                project_path,
                file_path,
            )

        except (
            FileNotFoundError,
            PermissionError,
            IsADirectoryError,
        ):
            continue

        content = file_data["content"]

        remaining_chars = (
            MAX_TOTAL_CHARS
            - total_chars
        )

        allowed_chars = min(
            MAX_FILE_CHARS,
            remaining_chars,
        )

        truncated = (
            len(content)
            > allowed_chars
        )

        if truncated:
            content = content[
                :allowed_chars
            ]

        file_contexts.append(
            {
                "file_path": file_data[
                    "file_path"
                ],
                "content": content,
                "truncated": truncated,
            }
        )

        total_chars += len(content)

    context_text = format_context(
        project,
        file_contexts,
    )

    return {
        "project": {
            "project_path": project[
                "project_path"
            ],
            "total_files": project[
                "total_files"
            ],
            "project_info": project[
                "project_info"
            ],
        },
        "files_in_context": [
            file["file_path"]
            for file in file_contexts
        ],
        "total_context_characters": len(
            context_text
        ),
        "context": context_text,
    }


def select_context_files(
    important_files: dict,
) -> list[str]:

    selected = []

    categories = [
        "entry_points",
        "api_files",
        "service_files",
        "configuration",
        "documentation",
    ]

    for category in categories:

        for file_path in important_files.get(
            category,
            [],
        ):

            if file_path not in selected:
                selected.append(file_path)

    return selected


def format_context(
    project: dict,
    file_contexts: list[dict],
) -> str:

    project_info = project[
        "project_info"
    ]

    lines = [
        "=== SAGE PROJECT CONTEXT ===",
        "",
        "PROJECT INFORMATION",
        (
            f"Project path: "
            f"{project['project_path']}"
        ),
        (
            f"Total files: "
            f"{project['total_files']}"
        ),
        (
            f"Language: "
            f"{project_info.get('language')}"
        ),
        (
            f"Package manager: "
            f"{project_info.get('package_manager')}"
        ),
        (
            f"Framework: "
            f"{project_info.get('framework')}"
        ),
        (
            f"Package file: "
            f"{project_info.get('package_file')}"
        ),
        "",
        "SOURCE FILES",
        "",
    ]

    for file_data in file_contexts:

        lines.append(
            (
                "--- FILE: "
                f"{file_data['file_path']} "
                "---"
            )
        )

        if file_data["truncated"]:
            lines.append(
                "[File content truncated "
                "for context size]"
            )

        lines.append(
            file_data["content"]
        )

        lines.append("")

        lines.append(
            (
                "--- END FILE: "
                f"{file_data['file_path']} "
                "---"
            )
        )

        lines.append("")

    return "\n".join(lines)