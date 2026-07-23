"""Unit and integration tests for Model Playground endpoints (S5-04a, S5-04b, S5-04c)."""

import io
from unittest.mock import AsyncMock, patch
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.api.playground import (
    router as playground_router,
    PlaygroundChatRequest,
    PlaygroundMessage,
    AttachmentInfo,
    ATTACHMENT_STORE,
)

app = FastAPI()
app.include_router(playground_router)

client = TestClient(app)


def test_playground_request_schemas():
    """Test Pydantic schemas for playground."""
    msg = PlaygroundMessage(role="user", content="Hello playground")
    req = PlaygroundChatRequest(model_id="gemini/gemini-3.5-flash", messages=[msg])
    assert req.model_id == "gemini/gemini-3.5-flash"
    assert len(req.messages) == 1
    assert req.messages[0].content == "Hello playground"
    assert req.stream is False


@patch("gateway.api.playground.completion_with_fallback", new_callable=AsyncMock)
def test_playground_chat_non_streaming(mock_completion):
    """Test POST /playground/chat non-streaming completion."""
    mock_completion.return_value = {
        "choices": [{"message": {"content": "Playground LLM response text"}}],
        "model": "gemini/gemini-3.5-flash",
        "usage": {"prompt_tokens": 15, "completion_tokens": 25},
    }

    response = client.post(
        "/playground/chat",
        json={
            "model_id": "gemini/gemini-3.5-flash",
            "messages": [{"role": "user", "content": "Tell me a joke"}],
            "temperature": 0.7,
            "max_tokens": 200,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Playground LLM response text"
    assert data["model_used"] == "gemini/gemini-3.5-flash"
    assert data["input_tokens"] == 15
    assert data["output_tokens"] == 25
    assert data["status"] == "success"


def test_playground_upload_text_file():
    """Test uploading a text file and extracting text."""
    file_content = b"This is sample document content for playground context."
    file_obj = io.BytesIO(file_content)

    response = client.post(
        "/playground/upload",
        files={"file": ("sample.txt", file_obj, "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "attachment_id" in data
    assert data["filename"] == "sample.txt"
    assert data["file_type"] == "txt"
    assert "sample document content" in data["extracted_text_preview"]

    att_id = data["attachment_id"]

    # Verify GET attachment details
    get_res = client.get(f"/playground/attachments/{att_id}")
    assert get_res.status_code == 200
    att_data = get_res.json()
    assert att_data["filename"] == "sample.txt"
    assert "sample document content" in att_data["extracted_text"]

    # Delete attachment
    del_res = client.delete(f"/playground/attachments/{att_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "deleted"


def test_playground_upload_unsupported_file():
    """Test uploading an invalid extension raises 400 error."""
    file_obj = io.BytesIO(b"binary data")
    response = client.post(
        "/playground/upload",
        files={"file": ("program.exe", file_obj, "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]
