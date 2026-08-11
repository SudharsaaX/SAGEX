from pathlib import Path
import shutil
import uuid
import zipfile


WORKSPACE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "workspaces"
)


def create_workspace(
    project_name: str,
) -> dict:
    """
    Create an isolated workspace for an uploaded project.
    """

    WORKSPACE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    project_id = uuid.uuid4().hex

    safe_name = (
        Path(project_name).stem
        or "project"
    )

    workspace = (
        WORKSPACE_ROOT
        / project_id
    )

    workspace.mkdir(
        parents=True,
        exist_ok=False,
    )

    return {
        "project_id": project_id,
        "project_name": safe_name,
        "workspace_path": str(
            workspace.resolve()
        ),
    }


def extract_project_zip(
    zip_path: str,
    workspace_path: str,
) -> dict:
    """
    Safely extract an uploaded project ZIP.

    Prevents files from escaping the workspace
    through path traversal.
    """

    workspace = (
        Path(workspace_path)
        .resolve()
    )

    if not workspace.exists():
        raise FileNotFoundError(
            "Workspace does not exist."
        )

    if not workspace.is_dir():
        raise NotADirectoryError(
            "Workspace path is not a directory."
        )

    zip_file = (
        Path(zip_path)
        .resolve()
    )

    if not zip_file.exists():
        raise FileNotFoundError(
            "Uploaded ZIP file was not found."
        )

    if not zip_file.is_file():
        raise ValueError(
            "Uploaded project is not a file."
        )

    extracted_files = 0

    with zipfile.ZipFile(
        zip_file,
        "r",
    ) as archive:

        for member in archive.infolist():

            member_path = (
                workspace
                / member.filename
            ).resolve()

            try:
                member_path.relative_to(
                    workspace
                )

            except ValueError:
                raise PermissionError(
                    "The uploaded archive "
                    "contains an unsafe path."
                )

            if member.is_dir():
                member_path.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                continue

            member_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with archive.open(
                member,
                "r",
            ) as source:

                with member_path.open(
                    "wb"
                ) as destination:

                    shutil.copyfileobj(
                        source,
                        destination,
                    )

            extracted_files += 1

    return {
        "status": "success",
        "workspace_path": str(
            workspace
        ),
        "extracted_files": extracted_files,
    }


def get_workspace(
    project_id: str,
) -> Path:
    """
    Return the workspace path for a project ID.
    """

    workspace = (
        WORKSPACE_ROOT
        / project_id
    ).resolve()

    try:
        workspace.relative_to(
            WORKSPACE_ROOT.resolve()
        )

    except ValueError:
        raise PermissionError(
            "Invalid project ID."
        )

    if not workspace.exists():
        raise FileNotFoundError(
            "Project workspace was not found."
        )

    if not workspace.is_dir():
        raise NotADirectoryError(
            "Project workspace is not a directory."
        )

    return workspace