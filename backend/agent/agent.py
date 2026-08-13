import json
import re

from ollama import Client

from project_tools.files import read_file
from project_tools.search import search_project
from project_tools.listing import list_files
from project_tools.workspace import Workspace


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
                                "type": "string"
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
                                "type": "string"
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
            }
        ]

        messages = [
            {
                "role": "system",
                "content": """
You are SAGE-X, a local AI software development assistant.

You are working inside a real software project.

You have these tools:

read_file
- Read the contents of a specific project file.

search_project
- Find files containing a specific word, phrase, function,
  class, variable, or code pattern.

list_files
- List project files.

IMPORTANT BEHAVIOR:

If the user asks about a specific file:
use read_file.

If the user asks where something exists:
use search_project.

If the user asks how a feature or system works:
first search the project for relevant terms,
then read the relevant files,
then explain the result.

If the user asks about the overall project:
inspect relevant files before answering.

Never pretend that you inspected a file when you did not.

When a tool is needed, output ONLY:

{
  "name": "tool_name",
  "arguments": {
    "argument": "value"
  }
}
"""
            },
            {
                "role": "user",
                "content": command
            }
        ]

        # ---------------------------------------------------------
        # AGENT LOOP
        # ---------------------------------------------------------

        max_steps = 8

        for _ in range(max_steps):

            response = client.chat(
                model="qwen2.5-coder:7b",
                messages=messages,
                tools=tools
            )

            # -----------------------------------------------------
            # Native Ollama tool call
            # -----------------------------------------------------

            if response.message.tool_calls:

                messages.append(response.message)

                for tool_call in response.message.tool_calls:

                    name = tool_call.function.name
                    arguments = tool_call.function.arguments

                    result = self.execute_tool(
                        name,
                        arguments
                    )

                    messages.append({
                        "role": "tool",
                        "content": str(result)
                    })

                continue

            # -----------------------------------------------------
            # JSON returned as normal text
            # -----------------------------------------------------

            content = response.message.content.strip()

            tool_request = self.extract_tool_request(content)

            if tool_request:

                name = tool_request.get("name")
                arguments = tool_request.get("arguments", {})

                result = self.execute_tool(
                    name,
                    arguments
                )

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
{result}
--- END TOOL RESULT ---

Continue working on the original request.

If more project information is required, request another appropriate
tool.

If you have enough information, provide the final answer.

Do not output JSON.
Do not describe the tool call.
"""
                })

                continue

            # -----------------------------------------------------
            # Normal final answer
            # -----------------------------------------------------

            return content

        return "I reached the project-analysis step limit before completing the request."

    # =============================================================
    # TOOL EXECUTION
    # =============================================================

    def execute_tool(self, name, arguments):

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

        return "Unknown tool."

    # =============================================================
    # TOOL REQUEST EXTRACTION
    # =============================================================

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