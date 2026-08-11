from pathlib import Path
import py_compile


def verify_changed_file(
    project_path: str,
    file_path: str,
) -> dict:
    """
    Verify a changed project file.

    Python files are checked using py_compile.
    Other file types are currently considered
    successfully verified if the file exists.
    """

    root = Path(
        project_path
    ).resolve()

    target = (
        root / file_path
    ).resolve()

    # -----------------------------------------
    # Security: prevent path traversal
    # -----------------------------------------

    try:
        target.relative_to(root)

    except ValueError:
        raise PermissionError(
            "The requested file is outside "
            "the project directory."
        )

    # -----------------------------------------
    # File validation
    # -----------------------------------------

    if not target.exists():
        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    if not target.is_file():
        raise IsADirectoryError(
            f"Path is not a file: {file_path}"
        )

    # -----------------------------------------
    # Python verification
    # -----------------------------------------

    if target.suffix.lower() == ".py":

        try:
            py_compile.compile(
                str(target),
                doraise=True,
            )

            return {
                "status": "passed",
                "file_path": file_path,
                "verification": "python_syntax",
                "message": (
                    "Python syntax verification "
                    "passed."
                ),
            }

        except py_compile.PyCompileError as error:

            return {
                "status": "failed",
                "file_path": file_path,
                "verification": "python_syntax",
                "message": (
                    "Python syntax verification "
                    "failed."
                ),
                "error": str(error),
            }

    # -----------------------------------------
    # Other file types
    # -----------------------------------------

    return {
        "status": "passed",
        "file_path": file_path,
        "verification": "file_exists",
        "message": (
            "File exists. No syntax verifier "
            "is currently configured for this "
            "file type."
        ),
    }