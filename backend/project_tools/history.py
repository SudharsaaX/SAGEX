import json
from datetime import datetime, timezone


HISTORY_DIR = ".sage-x"
HISTORY_FILE = "history.json"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _history_path(workspace):
    return workspace.get_path(f"{HISTORY_DIR}/{HISTORY_FILE}")


def _load_history(workspace):
    path = _history_path(workspace)

    if not path.exists():
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _save_history(workspace, history):
    path = _history_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(history, indent=2),
        encoding="utf-8"
    )


def _summarize_change(change):
    user_request = change.get("user_request") or "No user request recorded."
    file_path = change.get("file_path")

    return f"Changed {file_path} for request: {user_request}"


def record_change(workspace, change):
    history = _load_history(workspace)

    record = {
        "history_id": f"hist_{len(history) + 1:03d}",
        "change_id": change["change_id"],
        "file_path": change["file_path"],
        "user_request": change.get("user_request"),
        "summary": _summarize_change(change),
        "status": change["status"],
        "created_at": change.get("created_at"),
        "approved_at": change.get("approved_at"),
        "applied_at": change.get("applied_at"),
        "recorded_at": _now(),
        "diff": change.get("diff", ""),
    }

    history.append(record)
    _save_history(workspace, history)

    return record


def list_history(workspace, limit=20):
    history = _load_history(workspace)
    return history[-limit:]
