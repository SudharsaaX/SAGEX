import json
import re

from ollama import Client

from project_tools.files import read_file
from project_tools.search import search_project
from project_tools.listing import list_files
from project_tools.history import list_history as get_history
from project_tools.workspace import Workspace
from project_tools.approval import create_change


client = Client(host="http://localhost:11434")


class SageAgent:

    def __init__(self, project_path):
        self.workspace = Workspace(project_path)

    def process(self, command):

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read a file from the selected project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path relative to the project root."
                            }
                        },
                        "required": ["file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_project",
                    "description": "Search project files for text or code.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Text, function, class, variable, or code pattern to search for."
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List files in the selected project.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_history",
                    "description": (
                        "List recent SAGE-X change history records. "
                        "Use this to answer questions about previous changes, why files changed, "
                        "or what SAGE-X changed recently."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of recent history records to return."
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "propose_change",
                    "description": (
                        "Propose a modification to a project file. "
                        "Do not directly modify the file. "
                        "Use this after inspecting the relevant files."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "file_path": {
                                "type": "string",
                                "description": "Path relative to the project root."
                            },
                            "content": {
                                "type": "string",
                                "description": "The complete new content of the file."
                            }
                        },
                        "required": ["file_path", "content"]
                    }
                }
            }
        ]

        messages = [
            {
                "role": "system",
                "content": """
You are SAGE-X, a local AI software development assistant.

You work inside a real software project.

AVAILABLE TOOLS:

read_file
- Read a project file.

search_project
- Search project files for text or code.

list_files
- List project files.

list_history
- List recent SAGE-X change history records.
- Use this for questions like:
  "What was the last change?"
  "Show recent changes."
  "Why did we change a file?"
  "What did SAGE-X modify?"

propose_change
- Propose a modification to a project file.
- NEVER directly modify files.
- The user must approve the proposed change before it is written.
- When the user asks for a modification, call this tool after inspecting the relevant files.
- Do NOT ask the user whether they want you to propose the change.

BEHAVIOR:

If the user asks about a specific file:
use read_file.

If the user asks where something exists:
use search_project.

If the user asks how a feature works:
search first, then read relevant files.

If the user asks about previous changes or change history:
use list_history.

If the user asks for a code modification:
1. Find the relevant files.
2. Read the relevant files.
3. Understand the existing implementation.
4. Decide what needs to change.
5. Use propose_change.
6. NEVER pretend the modification has already been applied.

If a change is proposed, return the change information clearly.

Do not control approval yourself.
SAGE-X owns approval state.
After propose_change is called, SAGE-X will return the change ID and approval instructions.

IMPORTANT:
You are allowed to inspect files and propose changes.
You are NOT allowed to directly write files.

When you need a tool, use the available tool calling mechanism.
"""
            },
            {
                "role": "user",
                "content": command
            }
        ]

        max_steps = 12

        for _ in range(max_steps):

            response = client.chat(
                model="qwen2.5-coder:7b",
                messages=messages,
                tools=tools
            )

            # Native Ollama tool calls
            if response.message.tool_calls:

                messages.append(response.message)

                for tool_call in response.message.tool_calls:

                    name = tool_call.function.name
                    arguments = tool_call.function.arguments

                    result = self.execute_tool(
                        name,
                        arguments,
                        command
                    )

                    if name == "propose_change" and result.get("status") == "PENDING_APPROVAL":
                        return self.format_change_proposal(result)

                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result)
                    })

                continue

            # Normal response
            content = response.message.content.strip()

            # Fallback for models returning JSON instead of native tools
            tool_request = self.extract_tool_request(content)

            if tool_request:

                name = tool_request.get("name")
                arguments = tool_request.get("arguments", {})

                result = self.execute_tool(
                    name,
                    arguments,
                    command
                )

                if name == "propose_change" and result.get("status") == "PENDING_APPROVAL":
                    return self.format_change_proposal(result)

                messages.append({
                    "role": "assistant",
                    "content": content
                })

                messages.append({
                    "role": "user",
                    "content": f"""
SAGE-X executed the `{name}` tool.

Tool result:

--- BEGIN TOOL RESULT ---
{json.dumps(result)}
--- END TOOL RESULT ---

Continue working on the original request.

If another tool is required, use it.

If you have enough information, provide the final answer.
"""
                })

                continue

            return content

        return "SAGE-X reached its maximum reasoning steps."

    def execute_tool(self, name, arguments, user_request=None):

        if name == "read_file":

            return read_file(
                self.workspace,
                arguments["file_path"]
            )

        if name == "search_project":

            return search_project(
                self.workspace,
                arguments["query"]
            )

        if name == "list_files":

            return list_files(
                self.workspace
            )

        if name == "list_history":

            limit = arguments.get("limit", 20)

            return get_history(
                self.workspace,
                limit
            )

        if name == "propose_change":

            file_path = arguments["file_path"]
            new_content = arguments["content"]

            path = self.workspace.get_path(file_path)

            if path.exists() and path.is_file():
                old_content = path.read_text(encoding="utf-8")
            else:
                old_content = ""

            change = create_change(
                file_path,
                old_content,
                new_content,
                user_request
            )

            return change

        return {
            "error": f"Unknown tool: {name}"
        }

    def format_change_proposal(self, change):
        return f"""CHANGE PROPOSED

File:
{change["file_path"]}

Change ID:
{change["change_id"]}

Status:
{change["status"]}

Diff:
{change["diff"]}

Approve with:
POST /approve/{change["change_id"]}"""

    def extract_tool_request(self, content):

        try:

            data = json.loads(content)

            if (
                isinstance(data, dict)
                and "name" in data
                and "arguments" in data
            ):
                return data

        except json.JSONDecodeError:
            pass

        match = re.search(
            r'\{.*"name"\s*:\s*".*?".*"arguments"\s*:\s*\{.*\}.*\}',
            content,
            re.DOTALL
        )

        if match:

            try:

                data = json.loads(match.group(0))

                if (
                    isinstance(data, dict)
                    and "name" in data
                    and "arguments" in data
                ):
                    return data

            except json.JSONDecodeError:
                pass

        return None
