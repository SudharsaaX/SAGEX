from datetime import datetime, timezone
from difflib import unified_diff


pending_changes = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _next_change_id():
    return f"chg_{len(pending_changes) + 1:03d}"


def create_change(file_path, old_content, new_content, user_request):
    change_id = _next_change_id()

    diff = "".join(
        unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )

    pending_changes[change_id] = {
        "change_id": change_id,
        "file_path": file_path,
        "old_content": old_content,
        "new_content": new_content,
        "user_request": user_request,
        "status": "PENDING_APPROVAL",
        "created_at": _now(),
        "approved_at": None,
        "applied_at": None,
        "diff": diff,
    }

    return pending_changes[change_id]


def get_change(change_id):
    return pending_changes.get(change_id)


def mark_change_approved(change_id):
    change = get_change(change_id)

    if change:
        change["status"] = "APPROVED"
        change["approved_at"] = _now()

    return change


def mark_change_applied(change_id):
    change = get_change(change_id)

    if change:
        change["status"] = "APPLIED"
        change["applied_at"] = _now()

    return change


def mark_change_rejected(change_id):
    change = get_change(change_id)

    if change:
        change["status"] = "REJECTED"
        change["rejected_at"] = _now()

    return change
