from pathlib import Path

import ollama

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)

from fastapi.responses import StreamingResponse

from pydantic import BaseModel


from backend.services.backup_manager import (
    create_backup,
)

from backend.services.change_history import (
    clear_change_history,
    get_change_history,
    record_change,
)

from backend.services.change_planner import (
    create_change_plan,
)

from backend.services.change_transaction import (
    run_change_transaction,
)

from backend.services.change_verifier import (
    verify_changed_file,
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

from backend.services.project_executor import (
    get_project_logs,
    get_project_status,
    infer_start_command,
    start_project,
    stop_project,
)

from backend.services.rollback_manager import (
    rollback_change,
)

from backend.services.test_runner import (
    run_project_tests,
)

from backend.services.workspace_manager import (
    create_workspace,
    extract_project_zip,
    get_workspace,
)


# =========================================================
# APPLICATION
# =========================================================

app = FastAPI(
    title="SAGE",
    description=(
        "Software Assistant for Guidance & Execution"
    ),
    version="0.1.0",
)


# =========================================================
# REQUEST MODELS
# =========================================================


class CommandRequest(BaseModel):
    project_id: str
    command: str


class ProjectAnalysisRequest(BaseModel):
    project_path: str


class FileReadRequest(BaseModel):
    project_path: str
    file_path: str


class ChangePlanRequest(BaseModel):
    project_id: str
    command: str


class CodeModificationRequest(BaseModel):
    project_id: str
    command: str


class ApplyChangeRequest(BaseModel):
    project_id: str
    file_path: str
    operation: str
    anchor: str
    code: str
    approved: bool = False
    run_tests: bool = False


class ChangeSetItem(BaseModel):
    file_path: str
    operation: str
    anchor: str = ""
    code: str = ""
    reason: str | None = None


class ApplyChangeSetRequest(BaseModel):
    project_id: str
    changes: list[ChangeSetItem]
    approved: bool = False
    run_tests: bool = False



# =========================================================
# ROOT
# =========================================================


@app.get("/")
def root():
    return {
        "name": "SAGE",
        "version": app.version,
        "status": "running",
        "message": (
            "Software Assistant for Guidance & Execution"
        ),
    }


# =========================================================
# HEALTH
# =========================================================


@app.get("/health")
def health_check():
    return {
        "name": "SAGE",
        "version": app.version,
        "status": "healthy",
        "message": "SAGE application is running.",
    }


# =========================================================
# VERSION
# =========================================================


@app.get("/version")
def version_check():
    return {
        "name": "SAGE",
        "version": app.version,
    }


# =========================================================
# UPLOAD PROJECT
# =========================================================


@app.post("/projects/upload")
async def upload_project(
    file: UploadFile = File(...),
):
    """
    Upload a project ZIP file and create
    an isolated SAGE workspace.
    """

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="No project file was provided.",
        )

    filename = file.filename

    if not filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail=(
                "Only ZIP project uploads "
                "are currently supported."
            ),
        )

    temporary_zip = None

    try:
        # -------------------------------------------------
        # Create isolated workspace
        # -------------------------------------------------

        workspace_info = create_workspace(
            Path(filename).stem
        )

        workspace_path = Path(
            workspace_info["workspace_path"]
        )

        # -------------------------------------------------
        # Save uploaded ZIP temporarily
        # -------------------------------------------------

        temporary_zip = (
            workspace_path
            / "_uploaded_project.zip"
        )

        with temporary_zip.open("wb") as destination:

            while True:

                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                destination.write(chunk)

        # -------------------------------------------------
        # Extract project
        # -------------------------------------------------

        extraction = extract_project_zip(
            zip_path=str(temporary_zip),
            workspace_path=str(workspace_path),
        )

        # -------------------------------------------------
        # Delete temporary ZIP
        # -------------------------------------------------

        temporary_zip.unlink(
            missing_ok=True
        )

        return {
            "status": "success",
            "message": (
                "Project uploaded successfully."
            ),
            "project_id": (
                workspace_info["project_id"]
            ),
            "project_name": (
                workspace_info["project_name"]
            ),
            "workspace_path": (
                workspace_info["workspace_path"]
            ),
            "extracted_files": (
                extraction["extracted_files"]
            ),
        }

    except PermissionError as error:

        if temporary_zip:
            temporary_zip.unlink(
                missing_ok=True
            )

        raise HTTPException(
            status_code=403,
            detail=str(error),
        )

    except FileNotFoundError as error:

        if temporary_zip:
            temporary_zip.unlink(
                missing_ok=True
            )

        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except NotADirectoryError as error:

        if temporary_zip:
            temporary_zip.unlink(
                missing_ok=True
            )

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:

        if temporary_zip:
            temporary_zip.unlink(
                missing_ok=True
            )

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        if temporary_zip:
            temporary_zip.unlink(
                missing_ok=True
            )

        raise HTTPException(
            status_code=500,
            detail=(
                "Project upload failed: "
                f"{error}"
            ),
        )


# =========================================================
# GET PROJECT
# =========================================================


@app.get("/projects/{project_id}")
def get_project(
    project_id: str,
):
    """
    Get information about an uploaded project.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        files = []

        for path in workspace.rglob("*"):

            if path.is_file():

                relative_path = (
                    path.relative_to(
                        workspace
                    )
                )

                files.append(
                    str(relative_path)
                )

        files.sort()

        return {
            "status": "success",
            "project_id": project_id,
            "workspace_path": str(
                workspace
            ),
            "files": files,
            "file_count": len(files),
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )


# =========================================================
# ANALYZE UPLOADED PROJECT
# =========================================================


@app.get("/projects/{project_id}/analyze")
def analyze_uploaded_project(
    project_id: str,
):
    """
    Analyze an uploaded project using its project ID.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        analysis = scan_project(
            str(workspace)
        )

        return {
            "status": "success",
            "project_id": project_id,
            "workspace_path": str(
                workspace
            ),
            "analysis": analysis,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Project analysis failed: "
                f"{error}"
            ),
        )


# =========================================================
# AI COMMAND
# =========================================================


@app.post("/command")
def receive_command(
    request: CommandRequest,
):
    """
    Send a natural-language command to SAGE.

    The project ID is resolved internally to
    the isolated project workspace.
    """

    try:

        workspace = get_workspace(
            request.project_id
        )

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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    workspace_path = str(
        workspace
    )

    # -----------------------------------------------------
    # Build project context
    # -----------------------------------------------------

    try:

        project_context = (
            build_project_context(
                workspace_path
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

    # -----------------------------------------------------
    # Generate streaming AI response
    # -----------------------------------------------------

    def generate_response():

        system_prompt = (
            "You are SAGE, an AI "
            "software development "
            "assistant.\n\n"

            "You are working on the "
            "uploaded project provided "
            "by the user.\n\n"

            "Understand the actual project "
            "before suggesting changes.\n\n"

            "Never invent files, functions, "
            "components, dependencies, or "
            "project structure.\n\n"

            "When the user asks for a code "
            "modification, identify the "
            "relevant existing files and "
            "explain what should change.\n\n"

            "Actual modifications must go "
            "through SAGE's validated change "
            "pipeline."
        )

        if project_context:

            if isinstance(
                project_context,
                dict,
            ):

                context_text = (
                    project_context.get(
                        "context",
                        str(project_context),
                    )
                )

            else:

                context_text = str(
                    project_context
                )

            system_prompt += (
                "\n\n"
                "PROJECT CONTEXT:\n"
                + context_text
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
# ANALYZE PROJECT USING DIRECT PATH
# =========================================================


@app.post("/analyze-project")
def analyze_project(
    request: ProjectAnalysisRequest,
):
    """
    Analyze a project using a filesystem path.

    Kept for backend development/testing.
    Uploaded projects should use project_id.
    """

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
# READ FILE
# =========================================================


@app.post("/read-file")
def read_file(
    request: FileReadRequest,
):
    """
    Read a file from a project.

    Kept for backend development/testing.
    """

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
# PROJECT CONTEXT
# =========================================================


@app.post("/project-context")
def project_context(
    request: ProjectAnalysisRequest,
):
    """
    Build context from a project.

    Kept for backend development/testing.
    """

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
# CHANGE PLAN
# =========================================================


@app.post("/plan-change")
def plan_change(
    request: ChangePlanRequest,
):
    """
    Create a structured change plan for
    an uploaded SAGE project.
    """

    try:

        workspace = get_workspace(
            request.project_id
        )

        plan_result = create_change_plan(
            str(workspace),
            request.command,
        )

        return {
            "status": "success",
            "project_id": request.project_id,
            "plan": plan_result.get(
                "plan",
                plan_result,
            ),
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Change planning failed: "
                f"{error}"
            ),
        )


# =========================================================
# PROPOSE CODE CHANGE
# =========================================================


@app.post("/propose-change")
def propose_change(
    request: CodeModificationRequest,
):
    """
    Generate a proposed code modification
    for an uploaded SAGE project.

    This endpoint DOES NOT modify files.

    It generates and validates a structured
    patch that can later be submitted to
    /apply-change after user approval.
    """

    try:

        # -------------------------------------------------
        # Resolve project ID
        # -------------------------------------------------

        workspace = get_workspace(
            request.project_id
        )

        # -------------------------------------------------
        # Generate proposed code changes
        # -------------------------------------------------

        result = generate_code_changes(
            str(workspace),
            request.command,
        )

        return {
            "status": "success",
            "project_id": request.project_id,
            "proposal": result,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Code modification proposal "
                f"failed: {error}"
            ),
        )


# =========================================================
# APPLY CHANGE
# =========================================================


@app.post("/apply-change")
def apply_change(
    request: ApplyChangeRequest,
):
    """
    Validate, backup, apply, verify,
    and automatically rollback a change
    when verification fails.

    The project is identified using project_id.
    """

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

    # -----------------------------------------------------
    # Resolve workspace
    # -----------------------------------------------------

    try:

        workspace = get_workspace(
            request.project_id
        )

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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    project_path = str(
        workspace
    )

    try:

        # -------------------------------------------------
        # STEP 1: Validate patch
        # -------------------------------------------------

        validate_patch(
            project_path=project_path,
            file_path=request.file_path,
            operation=request.operation,
            anchor=request.anchor,
            code=request.code,
        )

        # -------------------------------------------------
        # STEP 2: Create backup
        # -------------------------------------------------

        backup_path = create_backup(
            project_path=project_path,
            file_path=request.file_path,
        )

        # -------------------------------------------------
        # STEP 3: Apply patch
        # -------------------------------------------------

        result = apply_patch(
            project_path=project_path,
            file_path=request.file_path,
            operation=request.operation,
            anchor=request.anchor,
            code=request.code,
        )

        # -------------------------------------------------
        # STEP 4: Verify
        # -------------------------------------------------

        verification = verify_changed_file(
            project_path=project_path,
            file_path=request.file_path,
        )

        # -------------------------------------------------
        # STEP 5: Rollback if verification fails
        # -------------------------------------------------

        if verification["status"] != "passed":

            rollback_result = rollback_change(
                project_path=project_path,
                file_path=request.file_path,
            )

            history_entry = record_change(
                project_path=project_path,
                file_path=request.file_path,
                operation=request.operation,
                status="failed",
                verification_status=(
                    verification["status"]
                ),
                rollback_status=(
                    rollback_result["status"]
                ),
                message=(
                    "Change failed verification "
                    "and was automatically rolled back."
                ),
            )

            return {
                "status": "failed",
                "project_id": request.project_id,
                "message": (
                    "Change was applied, but "
                    "verification failed. "
                    "The original file was restored."
                ),
                "backup_path": backup_path,
                "result": result,
                "verification": verification,
                "tests": {
                    "status": "skipped",
                    "reason": (
                        "Syntax verification failed "
                        "before running tests."
                    ),
                },
                "rollback": rollback_result,
                "history": history_entry,
            }

        # -------------------------------------------------
        # STEP 6: Automated Project Tests (Optional)
        # -------------------------------------------------

        tests_result = {
            "status": "skipped",
            "reason": (
                "Automated tests were not requested."
            ),
        }

        if request.run_tests:

            tests_result = run_project_tests(
                project_path=project_path
            )

            test_status = tests_result.get("status")

            if test_status in {"failed", "timeout"}:

                rollback_result = rollback_change(
                    project_path=project_path,
                    file_path=request.file_path,
                )

                fail_message = (
                    "Project tests failed. "
                    "The original file was restored."
                    if test_status == "failed"
                    else "Project tests timed out. "
                    "The original file was restored."
                )

                history_entry = record_change(
                    project_path=project_path,
                    file_path=request.file_path,
                    operation=request.operation,
                    status="failed",
                    verification_status=test_status,
                    rollback_status=(
                        rollback_result["status"]
                    ),
                    message=fail_message,
                )

                return {
                    "status": "failed",
                    "project_id": request.project_id,
                    "message": fail_message,
                    "backup_path": backup_path,
                    "result": result,
                    "verification": verification,
                    "tests": tests_result,
                    "rollback": rollback_result,
                    "history": history_entry,
                }

        # -------------------------------------------------
        # STEP 7: Record success
        # -------------------------------------------------

        test_status = tests_result.get("status")

        if test_status == "passed":

            ver_status = "passed"
            success_msg = (
                "Change applied, verified, "
                "and project tests passed."
            )

        elif test_status == "unsupported":

            ver_status = "unsupported"
            success_msg = (
                "Change applied and syntax "
                "verified, but project tests "
                "are unsupported."
            )

        else:

            ver_status = verification["status"]
            success_msg = (
                "Change applied and "
                "verified successfully."
            )

        history_entry = record_change(
            project_path=project_path,
            file_path=request.file_path,
            operation=request.operation,
            status="success",
            verification_status=ver_status,
            rollback_status=None,
            message=success_msg,
        )

        # -------------------------------------------------
        # STEP 8: Return success
        # -------------------------------------------------

        return {
            "status": "success",
            "project_id": request.project_id,
            "message": success_msg,
            "backup_path": backup_path,
            "result": result,
            "verification": verification,
            "tests": tests_result,
            "history": history_entry,
        }


    except PermissionError as error:

        if backup_path:

            try:

                rollback_change(
                    project_path=project_path,
                    file_path=request.file_path,
                )

            except Exception:
                pass

        raise HTTPException(
            status_code=403,
            detail=str(error),
        )

    except FileNotFoundError as error:

        if backup_path:

            try:

                rollback_change(
                    project_path=project_path,
                    file_path=request.file_path,
                )

            except Exception:
                pass

        raise HTTPException(
            status_code=404,
            detail=str(error),
        )

    except IsADirectoryError as error:

        if backup_path:

            try:

                rollback_change(
                    project_path=project_path,
                    file_path=request.file_path,
                )

            except Exception:
                pass

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:

        if backup_path:

            try:

                rollback_change(
                    project_path=project_path,
                    file_path=request.file_path,
                )

            except Exception:
                pass

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        if backup_path:

            try:

                rollback_change(
                    project_path=project_path,
                    file_path=request.file_path,
                )

            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=(
                "The change could not be completed: "
                f"{error}"
            ),
        )


# =========================================================
# APPLY CHANGE SET (MULTI-FILE ATOMIC TRANSACTION)
# =========================================================


@app.post("/apply-change-set")
def apply_change_set(
    request: ApplyChangeSetRequest,
):
    """
    Validate, backup, apply, verify, and optionally test a multi-file
    change set as a single atomic transaction.
    If ANY step fails, ALL modified files are automatically rolled back.
    """

    if not request.approved:

        raise HTTPException(
            status_code=400,
            detail=(
                "Change set was not approved. "
                "Set approved to true after "
                "reviewing the proposed changes."
            ),
        )

    try:

        workspace = get_workspace(
            request.project_id
        )

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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    project_path = str(
        workspace
    )

    try:

        changes_list = [
            item.dict()
            for item in request.changes
        ]

        result = run_change_transaction(
            project_path=project_path,
            changes=changes_list,
            run_tests=request.run_tests,
        )

        return {
            "status": result.get("status", "success"),
            "project_id": request.project_id,
            **result,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Multi-file change transaction "
                f"failed: {error}"
            ),
        )



# =========================================================
# CHANGE HISTORY
# =========================================================


@app.get("/change-history")
def change_history(
    project_id: str,
):
    """
    Get SAGE change history for an uploaded project.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        history = get_change_history(
            str(workspace)
        )

        return {
            "status": "success",
            "project_id": project_id,
            "history": history,
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

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# =========================================================
# CLEAR CHANGE HISTORY
# =========================================================


@app.delete("/change-history")
def clear_change_history_endpoint(
    project_id: str,
):
    """
    Clear SAGE change history for an uploaded project.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        result = clear_change_history(
            str(workspace)
        )

        return {
            "status": "success",
            "project_id": project_id,
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

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# =========================================================
# RUN PROJECT
# =========================================================


@app.post("/projects/{project_id}/run")
def run_project_endpoint(
    project_id: str,
):
    """
    Safely infer start command and start the project process
    in its isolated workspace.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        result = start_project(
            str(workspace)
        )

        return {
            "project_id": project_id,
            "workspace_path": str(workspace),
            **result,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Project execution failed: "
                f"{error}"
            ),
        )


# =========================================================
# PROJECT EXECUTION STATUS
# =========================================================


@app.get("/projects/{project_id}/status")
def get_project_status_endpoint(
    project_id: str,
):
    """
    Get current execution status (running, stopped, failed)
    for a project process.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        result = get_project_status(
            str(workspace)
        )

        return {
            "project_id": project_id,
            **result,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# =========================================================
# STOP PROJECT
# =========================================================


@app.post("/projects/{project_id}/stop")
def stop_project_endpoint(
    project_id: str,
):
    """
    Stop a SAGE-managed running project process cleanly.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        result = stop_project(
            str(workspace)
        )

        return {
            "project_id": project_id,
            **result,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# =========================================================
# GET PROJECT EXECUTION LOGS
# =========================================================


@app.get("/projects/{project_id}/logs")
def get_project_logs_endpoint(
    project_id: str,
):
    """
    Get captured stdout and stderr execution logs for a project.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        result = get_project_logs(
            str(workspace)
        )

        return {
            "project_id": project_id,
            **result,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error),
        )


# =========================================================
# RUN PROJECT TESTS
# =========================================================


@app.post("/projects/{project_id}/test")
def run_project_tests_endpoint(
    project_id: str,
):
    """
    Safely infer test framework (pytest or npm test) and execute
    automated project tests in its isolated workspace.
    """

    try:

        workspace = get_workspace(
            project_id
        )

        result = run_project_tests(
            str(workspace)
        )

        return {
            "status": "success",
            "project_id": project_id,
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

    except NotADirectoryError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "Project test execution failed: "
                f"{error}"
            ),
        )
