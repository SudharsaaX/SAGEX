import ollama

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.responses import (
    StreamingResponse,
)

from pydantic import BaseModel

from backend.services.change_planner import (
    create_change_plan,
)

from backend.services.code_modifier import (
    generate_code_changes,
)

from backend.services.context_builder import (
    build_project_context,
)

from backend.services.file_reader import (
    read_project_file,
)

from backend.services.project_analyzer import (
    scan_project,
)


app = FastAPI(
    title="SAGE",
    description=(
        "Software Assistant for "
        "Guidance & Execution"
    ),
    version="0.1.0",
)


class CommandRequest(BaseModel):
    command: str
    project_path: str | None = None


class ProjectAnalysisRequest(BaseModel):
    project_path: str


class FileReadRequest(BaseModel):
    project_path: str
    file_path: str


class ChangePlanRequest(BaseModel):
    project_path: str
    command: str


class CodeModificationRequest(BaseModel):
    project_path: str
    command: str


@app.get("/")
def root():
    return {
        "name": "SAGE",
        "version": "0.1.0",
        "status": "running",
        "message": (
            "Software Assistant for "
            "Guidance & Execution"
        ),
    }


@app.post("/command")
def receive_command(
    request: CommandRequest,
):
    project_context = None

    if request.project_path:
        try:
            project_context = (
                build_project_context(
                    request.project_path
                )
            )

        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404,
                detail=str(error),
            )

        except NotADirectoryError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error),
            )

    def generate_response():
        system_prompt = (
            "You are SAGE, an AI "
            "software development "
            "assistant. "

            "Give concise and "
            "practical answers. "

            "When a developer asks "
            "for a software change, "
            "focus on understanding "
            "the requested change "
            "rather than giving "
            "unnecessary explanations."
        )

        if project_context:
            system_prompt += (
                "\n\n"
                "You have access to "
                "the actual project "
                "context below. "

                "Use it to answer "
                "questions about "
                "the project. "

                "Do not invent files, "
                "components, functions, "
                "or dependencies that "
                "are not present in "
                "the context."

                "\n\n"
                + project_context[
                    "context"
                ]
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
                    "content": request.command,
                },
            ],
            stream=True,
            keep_alive="30m",
            options={
                "num_predict": 250,
                "num_ctx": 8192,
            },
        )

        for chunk in response:
            content = chunk[
                "message"
            ]["content"]

            if content:
                yield content

    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
    )


@app.post("/analyze-project")
def analyze_project(
    request: ProjectAnalysisRequest,
):
    try:
        project = scan_project(
            request.project_path
        )

        return {
            "status": "success",
            "project": project,
        }

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except NotADirectoryError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/read-file")
def read_file(
    request: FileReadRequest,
):
    try:
        file = read_project_file(
            request.project_path,
            request.file_path,
        )

        return {
            "status": "success",
            "file": file,
        }

    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail=str(error),
        )

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except IsADirectoryError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/project-context")
def project_context(
    request: ProjectAnalysisRequest,
):
    try:
        context = build_project_context(
            request.project_path
        )

        return {
            "status": "success",
            "context": context,
        }

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except NotADirectoryError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/plan-change")
def plan_change(
    request: ChangePlanRequest,
):
    try:
        plan = create_change_plan(
            request.project_path,
            request.command,
        )

        return plan

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except NotADirectoryError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


@app.post("/propose-change")
def propose_change(
    request: CodeModificationRequest,
):
    try:
        result = generate_code_changes(
            request.project_path,
            request.command,
        )

        return result

    except FileNotFoundError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except NotADirectoryError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )