from app.routers.transcribe import build_multipart_body


def test_build_multipart_body_includes_model_field():
    body, content_type = build_multipart_body(
        "recording.webm", b"fake-audio-bytes", "audio/webm", "whisper-large-v3-turbo"
    )
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="model"' in body
    assert b"whisper-large-v3-turbo" in body


def test_build_multipart_body_includes_file_field_and_bytes():
    body, _ = build_multipart_body(
        "recording.webm", b"fake-audio-bytes", "audio/webm", "whisper-large-v3-turbo"
    )
    assert b'name="file"; filename="recording.webm"' in body
    assert b"Content-Type: audio/webm" in body
    assert b"fake-audio-bytes" in body


def test_build_multipart_body_ends_with_closing_boundary():
    body, content_type = build_multipart_body("recording.webm", b"x", "audio/webm", "whisper-large-v3-turbo")
    boundary = content_type.split("boundary=")[1]
    assert body.rstrip(b"\r\n").endswith(f"--{boundary}--".encode("utf-8"))
