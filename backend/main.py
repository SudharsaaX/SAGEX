import ollama
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
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
    def generate_response():
        response = ollama.chat(
            model="qwen2.5-coder:7b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are SAGE, an AI software development assistant. "
                        "Give concise and practical answers. "
                        "When a developer asks for a software change, "
                        "focus on understanding the requested change "
                        "rather than giving unnecessary explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": request.command,
                },
            ],
            stream=True,
            keep_alive="30m",
            options={
                "num_predict": 300,
            },
        )

        for chunk in response:
            content = chunk["message"]["content"]

            if content:
                yield content

    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
    )