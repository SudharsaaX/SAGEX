from flask import Flask, request, jsonify
from agent.agent import SageAgent

from project_tools.approval import get_change
from project_tools.writer import write_file


app = Flask(__name__)

agent = None


@app.route("/workspace", methods=["POST"])
def set_workspace():
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

    result = write_file(
        agent.workspace,
        change["file_path"],
        change["content"]
    )

    return jsonify({
        "message": "Change approved",
        "result": result
    })


if __name__ == "__main__":
    app.run(debug=True)