from flask import Flask, request, jsonify
from flask_cors import CORS
import threading
import tkinter as tk
from tkinter import filedialog
from agent.agent import SageAgent
import subprocess

from project_tools.approval import (
    get_change,
    mark_change_approved,
    mark_change_applied,
    mark_change_rejected,
)
from project_tools.history import list_history, record_change
from project_tools.writer import write_file
from project_tools.listing import list_files
from project_tools.files import read_file as read_project_file


app = Flask(__name__)
CORS(app)

agent = None


@app.route("/workspace", methods=["POST"])
def set_workspace():
    global shell_process

    if shell_process is not None:
        try:
            shell_process.terminate()
        except Exception:
            pass

        shell_process = None
    
    global agent

    data = request.json
    project_path = data.get("project_path")

    if not project_path:
        return jsonify({"error": "Project path is required"}), 400

    agent = SageAgent(project_path)

    return jsonify({
        "message": "Workspace selected",
        "project": project_path
    })


@app.route("/command", methods=["POST"])
def command():
    if agent is None:
        return jsonify({"error": "Select a workspace first"}), 400

    data = request.json
    user_command = data.get("command")

    if not user_command:
        return jsonify({"error": "Command is required"}), 400

    response = agent.process(user_command)

    return jsonify({
        "response": response
    })


@app.route("/approve/<change_id>", methods=["POST"])
def approve(change_id):

    if agent is None:
        return jsonify({"error": "Select a workspace first"}), 400

    change = get_change(change_id)

    if not change:
        return jsonify({"error": "Change not found"}), 404

    if change["status"] == "APPLIED":
        return jsonify({
            "error": "Change has already been applied",
            "change_id": change_id,
            "status": change["status"]
        }), 400

    mark_change_approved(change_id)

    result = write_file(
        agent.workspace,
        change["file_path"],
        change["new_content"]
    )

    applied_change = mark_change_applied(change_id)
    history_record = record_change(agent.workspace, applied_change)

    return jsonify({
        "message": "Change approved",
        "change_id": change_id,
        "file_path": change["file_path"],
        "status": change["status"],
        "history_id": history_record["history_id"],
        "result": result
    })


@app.route("/history", methods=["GET"])
def history():
    if agent is None:
        return jsonify({"error": "Select a workspace first"}), 400

    limit = request.args.get("limit", default=20, type=int)

    return jsonify({
        "history": list_history(agent.workspace, limit)
    })


@app.route("/reject/<change_id>", methods=["POST"])
def reject(change_id):
    if agent is None:
        return jsonify({"error": "Select a workspace first"}), 400

    change = get_change(change_id)

    if not change:
        return jsonify({"error": "Change not found"}), 404

    if change["status"] == "APPLIED":
        return jsonify({
            "error": "Applied changes cannot be rejected",
            "change_id": change_id,
            "status": change["status"]
        }), 400

    rejected_change = mark_change_rejected(change_id)

    return jsonify({
        "message": "Change rejected",
        "change_id": change_id,
        "file_path": rejected_change["file_path"],
        "status": rejected_change["status"]
    })


@app.route("/files", methods=["GET"])
def files():
    if agent is None:
        return jsonify({"error": "Select a workspace first"}), 400

    files = list_files(agent.workspace)

    return jsonify({"files": files})


@app.route("/file", methods=["GET"])
def file_content():
    if agent is None:
        return jsonify({"error": "Select a workspace first"}), 400

    path = request.args.get("path")

    if not path:
        return jsonify({"error": "path parameter is required"}), 400

    content = read_project_file(agent.workspace, path)

    return jsonify({"path": path, "content": content})


@app.route("/pick_workspace", methods=["GET"])
def pick_workspace():
    """Open a native folder picker on the server machine and return the chosen path.

    Runs a synchronous Tk dialog on the server. This is intended for local
    development where the Flask process runs on the user's desktop. If the
    dialog is canceled or an error occurs, return a clear error message so
    the frontend can present a fallback UI.
    """
    try:
        root = tk.Tk()
        root.withdraw()
        # Try to bring the dialog to the front on Windows
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass

        folder = filedialog.askdirectory()
        try:
            root.destroy()
        except Exception:
            pass

        if not folder:
            return jsonify({"path": None, "error": "canceled"}), 200

        return jsonify({"path": folder}), 200
    except Exception as e:
        return jsonify({"path": None, "error": str(e)}), 500


shell_process = None
shell_lock = threading.Lock()


def start_shell():
    global shell_process

    if shell_process is not None:
        return shell_process

    shell_process = subprocess.Popen(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=str(agent.workspace.root),
    )

    return shell_process


@app.route("/terminal", methods=["POST"])
def terminal():
    global shell_process

    if agent is None:
        return jsonify({
            "error": "Select a workspace first"
        }), 400

    data = request.json or {}
    command = data.get("command", "").strip()

    if not command:
        return jsonify({
            "error": "Command is required"
        }), 400

    try:
        with shell_lock:
            process = start_shell()

            marker = "__SAGEX_COMMAND_DONE__"

            process.stdin.write(
                f"{command}\n"
                f"Write-Output '{marker}'\n"
            )
            process.stdin.flush()

            output = []

            while True:
                line = process.stdout.readline()

                if not line:
                    break

                line = line.rstrip("\r\n")

                if line == marker:
                    break

                output.append(line)

            return jsonify({
                "output": "\n".join(output),
                "cwd": str(agent.workspace.root),
            })

    except Exception as error:
        shell_process = None

        return jsonify({
            "error": str(error)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)
