from pathlib import Path
import hashlib
import shutil


def _get_backup_file(
    root: Path,
    target: Path,
) -> Path:
    """
    Generate a unique backup path for the target file.

    The relative project path is hashed so files with the
    same filename in different directories cannot overwrite
    each other's backups.
    """

    relative_path = target.relative_to(root)

    path_hash = hashlib.sha256(
        str(relative_path).encode("utf-8")
    ).hexdigest()[:12]

    backup_dir = (
        root / ".sage" / "backups"
    )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        backup_dir
        / f"{path_hash}_{target.name}"
    )


def _resolve_project_file(
    project_path: str,
    file_path: str,
) -> tuple[Path, Path]:
    """
    Resolve and validate a project file.
    """

    root = Path(
        project_path
    ).resolve()

    target = (
        root / file_path
    ).resolve()

    try:
        target.relative_to(root)

    except ValueError:
        raise PermissionError(
            "The requested file is outside "
            "the project directory."
        )

    if not target.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    if not target.is_file():
        raise IsADirectoryError(
            f"Path is not a file: {file_path}"
        )

    return root, target


def create_backup(
    project_path: str,
    file_path: str,
) -> str:
    """
    Create a backup of a project file before
    applying a code modification.
    """

    root, target = _resolve_project_file(
        project_path,
        file_path,
    )

    backup_file = _get_backup_file(
        root,
        target,
    )

    shutil.copy2(
        target,
        backup_file,
    )

    return str(
        backup_file
    )


def restore_backup(
    project_path: str,
    file_path: str,
) -> str:
    """
    Restore a project file from its backup.
    """

    root, target = _resolve_project_file(
        project_path,
        file_path,
    )

    backup_file = _get_backup_file(
        root,
        target,
    )

    if not backup_file.exists():
        raise FileNotFoundError(
            "Backup file was not found."
        )

    shutil.copy2(
        backup_file,
        target,
    )

    return str(
        target
    )