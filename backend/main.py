from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(
    title="SAGE",
    description="Software Assistant for Guidance & Execution",
    version="0.1.0",
)


class CommandRequest(BaseModel):
    command: str


@app.get("/")
def root():
    return {
        "name": "SAGE",
        "version": "0.1.0",
        "status": "running",
        "message": "Software Assistant for Guidance & Execution",
    }


@app.post("/command")
def receive_command(request: CommandRequest):
    return {
        "status": "received",
        "command": request.command,
        "message": f"SAGE received your command: {request.command}",
    }