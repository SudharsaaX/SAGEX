from backend.services.backup_manager import (
    restore_backup,
)


def rollback_change(
    project_path: str,
    file_path: str,
) -> dict:
    """
    Restore a project file from its most recent backup.

    This function is used when a code modification fails
    after a backup has already been created.
    """

    restored_path = restore_backup(
        project_path=project_path,
        file_path=file_path,
    )

    return {
        "status": "rolled_back",
        "file_path": file_path,
        "restored_path": restored_path,
        "message": (
            "The failed change was rolled back "
            "using the backup."
        ),
    }