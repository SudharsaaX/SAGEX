import json

import ollama

from backend.services.context_builder import (
    build_project_context,
)


def create_change_plan(
    project_path: str,
    command: str,
) -> dict:
    project_context = build_project_context(
        project_path
    )

    system_prompt = """
You are SAGE's change planning engine.

Your job is to analyze a developer's requested
software change using the provided project context.

Do NOT modify any files.

Do NOT provide full replacement source code.

Instead, determine:

1. What the developer wants.
2. Which existing files are most likely relevant.
3. What changes should be made.
4. What should remain unchanged.
5. What verification should be performed.

Return ONLY valid JSON using exactly this structure:

{
  "summary": "short description of the requested change",
  "relevant_files": [
    {
      "file_path": "path/to/file",
      "reason": "why this file is relevant"
    }
  ],
  "changes": [
    "specific change 1",
    "specific change 2"
  ],
  "unchanged": [
    "important existing behavior to preserve"
  ],
  "verification": [
    "verification step 1",
    "verification step 2"
  ]
}

Important rules:

- Use only files that exist in the provided project context.
- Do not invent filenames.
- Do not modify files.
- Keep the plan practical and concise.
- If the request is unclear, mention the uncertainty in the summary.
"""

    user_prompt = (
        "DEVELOPER REQUEST:\n"
        f"{command}\n\n"
        "PROJECT CONTEXT:\n"
        f"{project_context['context']}"
    )

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

    content = response["message"]["content"].strip()

    plan = parse_plan_response(content)

    return {
        "status": "success",
        "plan": plan,
    }


def parse_plan_response(content: str) -> dict:
    cleaned = content.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    try:
        plan = json.loads(cleaned)

    except json.JSONDecodeError:
        return {
            "summary": content,
            "relevant_files": [],
            "changes": [],
            "unchanged": [],
            "verification": [],
            "parse_error": True,
        }

    return plan