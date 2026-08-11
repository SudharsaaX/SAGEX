import ollama

from fastapi import (
    FastAPI,
    HTTPException,
)

from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from backend.services.backup_manager import (
    create_backup,
    restore_backup,
)

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

from backend.services.patch_applier import (
    apply_patch,
    validate_patch,
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


# =========================================================
# Request Models
# =========================================================


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


class ApplyChangeRequest(BaseModel):
    project_path: str
    file_path: str
    operation: str
    anchor: str
    code: str
    approved: bool


# =========================================================
# Root Endpoint
# =========================================================


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


# =========================================================
# Health Check
# =========================================================


@app.get("/health")
def health_check():
    return {
        "name": "SAGE",
        "version": "0.1.0",
        "status": "healthy",
        "message": (
            "SAGE application is running."
        ),
    }


# =========================================================
# Version
# =========================================================


@app.get("/version")
def version_check():
    return {
        "name": "SAGE",
        "version": "0.1.0",
    }


# =========================================================
# AI Command Endpoint
# =========================================================


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
                "context below.\n\n"

                "Use it to answer "
                "questions about "
                "the project.\n\n"

                "Do not invent files, "
                "components, functions, "
                "or dependencies that "
                "are not present in "
                "the context.\n\n"

                "PROJECT CONTEXT:\n"
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


# =========================================================
# Project Analysis
# =========================================================


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


# =========================================================
# Read Project File
# =========================================================


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


# =========================================================
# Project Context
# =========================================================


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


# =========================================================
# Change Planning
# =========================================================


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


# =========================================================
# Generate Code Change Proposal
# =========================================================


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


# =========================================================
# Apply Approved Change
# =========================================================


@app.post("/apply-change")
def apply_change(
    request: ApplyChangeRequest,
):
    if not request.approved:
        raise HTTPException(
            status_code=400,
            detail=(
                "Change was not approved. "
                "Set approved to true after "
                "reviewing the proposed change."
            ),
        )

    backup_path = None

    try:
        # -------------------------------------------------
        # Step 1: Validate patch first
        # -------------------------------------------------

        validate_patch(
            project_path=request.project_path,
            file_path=request.file_path,
            operation=request.operation,
            anchor=request.anchor,
            code=request.code,
        )

        # -------------------------------------------------
        # Step 2: Create backup only after validation
        # -------------------------------------------------

        backup_path = create_backup(
            project_path=request.project_path,
            file_path=request.file_path,
        )

        # -------------------------------------------------
        # Step 3: Apply validated patch
        # -------------------------------------------------

        result = apply_patch(
            project_path=request.project_path,
            file_path=request.file_path,
            operation=request.operation,
            anchor=request.anchor,
            code=request.code,
        )

        return {
            "status": "success",
            "message": (
                "Change applied successfully."
            ),
            "backup_path": backup_path,
            "result": result,
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

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception:
        # -------------------------------------------------
        # Restore original file if application fails
        # -------------------------------------------------

        if backup_path:
            try:
                restore_backup(
                    project_path=request.project_path,
                    file_path=request.file_path,
                )
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=(
                "The change could not be applied "
                "and the original file was restored."
            ),
        )
