from pathlib import Path
from datetime import datetime, timezone
import json


def _history_file(
    project_path: str,
) -> Path:
    """
    Return the path to the SAGE change history file.
    """

    root = Path(
        project_path
    ).resolve()

    history_dir = (
        root / ".sage"
    )

    history_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return (
        history_dir
        / "change_history.json"
    )


def _load_history(
    history_file: Path,
) -> list:
    """
    Load existing change history.

    If the history file does not exist or contains
    invalid JSON, return an empty history.
    """

    if not history_file.exists():
        return []

    try:

        content = history_file.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            return []

        data = json.loads(
            content
        )

        if isinstance(data, list):
            return data

        return []

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []


def record_change(
    project_path: str,
    file_path: str,
    operation: str,
    status: str,
    verification_status: str | None = None,
    rollback_status: str | None = None,
    message: str | None = None,
) -> dict:
    """
    Record a SAGE code change in change history.
    """

    history_file = _history_file(
        project_path
    )

    history = _load_history(
        history_file
    )

    next_id = 1

    if history:

        existing_ids = [
            item.get("id")
            for item in history
            if isinstance(
                item.get("id"),
                int,
            )
        ]

        if existing_ids:
            next_id = max(
                existing_ids
            ) + 1

    entry = {
        "id": next_id,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "file_path": file_path,
        "operation": operation,
        "status": status,
        "verification": (
            verification_status
        ),
        "rollback": (
            rollback_status
        ),
        "message": message,
    }

    history.append(
        entry
    )

    history_file.write_text(
        json.dumps(
            history,
            indent=2,
        ),
        encoding="utf-8",
    )

    return entry


def get_change_history(
    project_path: str,
) -> list:
    """
    Return the complete SAGE change history.
    """

    history_file = _history_file(
        project_path
    )

    return _load_history(
        history_file
    )


def clear_change_history(
    project_path: str,
) -> dict:
    """
    Delete the SAGE change history.
    """

    history_file = _history_file(
        project_path
    )

    if history_file.exists():

        history_file.unlink()

    return {
        "status": "success",
        "message": (
            "SAGE change history cleared."
        ),
    }