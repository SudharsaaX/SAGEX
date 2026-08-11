import ast
import json
import re

import ollama

from backend.services.change_planner import (
    create_change_plan,
)
from backend.services.file_reader import (
    read_project_file,
)


def generate_code_changes(
    project_path: str,
    command: str,
) -> dict:
    """
    Generate a safe, structured code-change proposal.

    This function does NOT modify project files.
    """

    plan_result = create_change_plan(
        project_path,
        command,
    )

    plan = plan_result["plan"]

    if plan.get("parse_error"):
        return {
            "status": "error",
            "message": (
                "SAGE could not create a valid "
                "change plan."
            ),
            "plan": plan,
            "proposed_changes": [],
            "applied": False,
        }

    proposed_changes = []

    for file_info in plan.get(
        "relevant_files",
        [],
    ):
        file_path = file_info.get(
            "file_path"
        )

        if not file_path:
            continue

        try:
            file_data = read_project_file(
                project_path,
                file_path,
            )

        except (
            FileNotFoundError,
            PermissionError,
            IsADirectoryError,
        ) as error:
            proposed_changes.append(
                {
                    "file_path": file_path,
                    "status": "error",
                    "message": str(error),
                }
            )
            continue

        modification = generate_file_patch(
            current_content=file_data["content"],
            file_path=file_path,
            command=command,
            plan=plan,
        )

        proposed_changes.append(
            modification
        )

    return {
        "status": "success",
        "plan": plan,
        "proposed_changes": proposed_changes,
        "applied": False,
    }


def generate_file_patch(
    current_content: str,
    file_path: str,
    command: str,
    plan: dict,
) -> dict:
    """
    Ask Qwen to generate a minimal structured patch.
    """

    system_prompt = """
You are SAGE's controlled code modification engine.

Your task is to propose ONE SMALL code change
for ONE existing source file.

You MUST NOT modify the actual file.

You MUST NOT return the complete file.

You MUST NOT use Markdown.

You MUST return ONLY valid JSON.

IMPORTANT:

The JSON must look exactly like this:

{
  "file_path": "backend/main.py",
  "operation": "insert",
  "anchor": "def root():",
  "code": "@app.get(\\"/health\\")\\ndef health_check():\\n    return {\\n        \\"status\\": \\"healthy\\"\\n    }",
  "reason": "Add the health endpoint."
}

IMPORTANT CODE RULES:

- The code field must contain actual source code.
- Do NOT use Markdown.
- Do NOT use Markdown links.
- Do NOT use mailto links.
- Do NOT generate text such as:
  [n@app.get](mailto:n@app.get)
- Do NOT generate HTML.
- Do NOT use triple quotes.
- Do NOT return ```json.
- Do NOT return ```python.
- Do NOT include explanations outside the JSON.
- The anchor must be copied exactly from the current file.
- Make the smallest possible change.
- Preserve existing functionality.
- Do not add unrelated dependencies.

Allowed operations:

insert
replace
append

For insert:
- anchor must exist in the current file.
- code contains only the new code.

For replace:
- anchor must contain the exact old code.
- code contains the replacement code.

For append:
- anchor must be an empty string.
- code contains the code to append.

Return valid JSON only.
"""

    user_prompt = (
        "DEVELOPER REQUEST:\n"
        f"{command}\n\n"
        "CHANGE PLAN:\n"
        f"{json.dumps(plan, indent=2)}\n\n"
        "TARGET FILE:\n"
        f"{file_path}\n\n"
        "CURRENT FILE CONTENT:\n"
        f"{current_content}"
    )

    try:
        response = ollama.chat(
            model="qwen2.5-coder:7b",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            stream=False,
            keep_alive="30m",
            options={
                "num_predict": 500,
                "num_ctx": 8192,
            },
        )

    except Exception as error:
        return {
            "operation": "",
            "anchor": "",
            "code": "",
            "reason": (
                "SAGE could not communicate "
                "with the local AI model."
            ),
            "parse_error": True,
            "file_path": file_path,
            "error": str(error),
        }

    raw_content = response[
        "message"
    ]["content"].strip()

    patch = parse_patch_response(
        raw_content
    )

    if patch.get("parse_error"):
        patch["file_path"] = file_path
        return patch

    patch["file_path"] = file_path

    validation = validate_patch(
        current_content=current_content,
        patch=patch,
    )

    patch.update(validation)

    return patch


def parse_patch_response(
    content: str,
) -> dict:
    """
    Parse Qwen's JSON response safely.
    """

    cleaned = content.strip()

    # Remove Markdown fences if the model
    # ignores the instruction.
    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned,
    )

    cleaned = cleaned.strip()

    try:
        result = json.loads(
            cleaned
        )

    except json.JSONDecodeError:

        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1:
            return invalid_patch(
                content
            )

        candidate = cleaned[
            start:end + 1
        ]

        try:
            result = json.loads(
                candidate
            )

        except json.JSONDecodeError:
            return invalid_patch(
                content
            )

    if not isinstance(
        result,
        dict,
    ):
        return invalid_patch(
            content
        )

    required_fields = [
        "operation",
        "anchor",
        "code",
        "reason",
    ]

    for field in required_fields:
        if field not in result:
            return invalid_patch(
                content,
                f"Missing required field: {field}",
            )

    return {
        "operation": result["operation"],
        "anchor": clean_generated_text(
            result["anchor"]
        ),
        "code": clean_generated_text(
            result["code"]
        ),
        "reason": clean_generated_text(
            result["reason"]
        ),
        "parse_error": False,
    }


def clean_generated_text(
    value: str,
) -> str:
    """
    Clean known formatting artifacts from
    model-generated text.
    """

    if not isinstance(
        value,
        str,
    ):
        return value

    # -----------------------------------------
    # Remove mailto artifacts
    # -----------------------------------------

    value = re.sub(
        r"\\?\[n@app\."
        r"(get|post|put|delete|patch)"
        r"\]"
        r"\(mailto\\?:n@app\."
        r"(get|post|put|delete|patch)"
        r"\)",
        lambda match: (
            "@app."
            + match.group(1)
        ),
        value,
    )

    # -----------------------------------------
    # Remove escaped Markdown-style artifacts
    # -----------------------------------------

    value = re.sub(
        r"\\?\[n@app\."
        r"(get|post|put|delete|patch)"
        r"\]",
        lambda match: (
            "@app."
            + match.group(1)
        ),
        value,
    )

    # -----------------------------------------
    # Newline artifacts
    # -----------------------------------------

    value = value.replace(
        "\\[n",
        "\n",
    )

    value = value.replace(
        r"\[n",
        "\n",
    )

    # -----------------------------------------
    # Escaped underscore
    # -----------------------------------------

    value = value.replace(
        r"\_",
        "_",
    )

    # -----------------------------------------
    # Escaped slash
    # -----------------------------------------

    value = value.replace(
        r"\/",
        "/",
    )

    return value


def invalid_patch(
    raw_response: str,
    message: str = (
        "Could not parse Qwen response."
    ),
) -> dict:
    return {
        "operation": "",
        "anchor": "",
        "code": "",
        "reason": message,
        "parse_error": True,
        "raw_response": raw_response,
    }


def validate_patch(
    current_content: str,
    patch: dict,
) -> dict:
    """
    Validate a proposed patch without applying it.
    """

    operation = patch.get(
        "operation"
    )

    anchor = patch.get(
        "anchor"
    )

    code = patch.get(
        "code"
    )

    # -----------------------------------------
    # Operation validation
    # -----------------------------------------

    if operation not in {
        "insert",
        "replace",
        "append",
    }:
        return {
            "validation": "failed",
            "validation_message": (
                "Unsupported patch operation."
            ),
        }

    # -----------------------------------------
    # Code must exist
    # -----------------------------------------

    if not isinstance(
        code,
        str,
    ):
        return {
            "validation": "failed",
            "validation_message": (
                "Generated code is not a string."
            ),
        }

    if not code.strip():
        return {
            "validation": "failed",
            "validation_message": (
                "Proposed code is empty."
            ),
        }

    # -----------------------------------------
    # Reject obvious model artifacts
    # -----------------------------------------

    forbidden_artifacts = [
        "mailto:",
        "mailto\\:",
        "[n@app.",
        "\\[n@app.",
        "```",
    ]

    for artifact in forbidden_artifacts:

        if artifact in code:
            return {
                "validation": "failed",
                "validation_message": (
                    "Generated code contains "
                    f"an invalid model artifact: "
                    f"{artifact}"
                ),
            }

    # -----------------------------------------
    # Append
    # -----------------------------------------

    if operation == "append":

        if anchor != "":
            return {
                "validation": "failed",
                "validation_message": (
                    "Append operation must "
                    "use an empty anchor."
                ),
            }

    # -----------------------------------------
    # Insert / Replace
    # -----------------------------------------

    else:

        if not anchor:
            return {
                "validation": "failed",
                "validation_message": (
                    "Patch anchor is empty."
                ),
            }

        if anchor not in current_content:
            return {
                "validation": "failed",
                "validation_message": (
                    "The proposed anchor does not "
                    "exist in the current file."
                ),
            }

    # -----------------------------------------
    # Replace anchor must be unique
    # -----------------------------------------

    if operation == "replace":

        occurrences = (
            current_content.count(
                anchor
            )
        )

        if occurrences != 1:
            return {
                "validation": "failed",
                "validation_message": (
                    "Replace anchor must occur "
                    "exactly once in the file."
                ),
            }

    # -----------------------------------------
    # Dangerous operations
    # -----------------------------------------

    dangerous_patterns = [
        "os.remove(",
        "os.unlink(",
        "shutil.rmtree(",
        "subprocess.run(",
        "subprocess.Popen(",
        "subprocess.call(",
        "os.system(",
    ]

    for pattern in dangerous_patterns:

        if pattern in code:
            return {
                "validation": "failed",
                "validation_message": (
                    "Patch contains a potentially "
                    "dangerous operation: "
                    f"{pattern}"
                ),
            }

    # -----------------------------------------
    # Python syntax validation
    # -----------------------------------------

    if file_path_is_python(
        patch.get("file_path", "")
    ):

        syntax_result = validate_python_code(
            code
        )

        if not syntax_result["valid"]:
            return {
                "validation": "failed",
                "validation_message": (
                    "Generated Python code "
                    "failed syntax validation: "
                    + syntax_result["error"]
                ),
            }

    return {
        "validation": "passed",
        "validation_message": (
            "Patch passed structural, "
            "artifact, safety, and syntax "
            "validation."
        ),
    }


def file_path_is_python(
    file_path: str,
) -> bool:
    return file_path.lower().endswith(
        ".py"
    )


def validate_python_code(
    code: str,
) -> dict:
    """
    Validate whether generated Python code
    is syntactically valid.

    For an insertion snippet, Python's AST parser
    may reject decorators without a following
    function, so we wrap decorator snippets when
    necessary.
    """

    test_code = code.strip()

    try:
        ast.parse(
            test_code
        )

        return {
            "valid": True,
            "error": "",
        }

    except SyntaxError:

        # If the generated snippet starts with
        # a decorator, test it together with a
        # temporary function.
        if test_code.startswith(
            "@"
        ):

            wrapped_code = (
                test_code
                + "\n"
                + "def __sage_validation_function__():\n"
                + "    pass\n"
            )

            try:
                ast.parse(
                    wrapped_code
                )

                return {
                    "valid": True,
                    "error": "",
                }

            except SyntaxError as error:
                return {
                    "valid": False,
                    "error": str(error),
                }

        return {
            "valid": False,
            "error": "Generated code is not valid Python.",
        }