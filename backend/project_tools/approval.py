pending_changes = {}


def create_change(file_path, content):
    change_id = str(len(pending_changes) + 1)

    pending_changes[change_id] = {
        "file_path": file_path,
        "content": content
    }

    return change_id


def get_change(change_id):
    return pending_changes.get(change_id)