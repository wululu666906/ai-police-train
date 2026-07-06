import asyncio
import json
from typing import Any

import websockets
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from pydantic import BaseModel

import database
import models
from routers.auth import ALGORITHM, SECRET_KEY, get_current_user
from services.speech_service import (
    QWEN_ASR_API_KEY,
    SpeechRecognitionError,
    build_realtime_session_update,
    build_realtime_url,
    extract_realtime_transcript,
    extract_realtime_transcript_delta,
    get_speech_status,
    transcribe_audio_data_url,
)

router = APIRouter(prefix="/speech", tags=["Speech"])


class SpeechTranscriptionRequest(BaseModel):
    audio_data_url: str
    language: str | None = "zh"
    enable_itn: bool = True


@router.get("/status")
def speech_status(_: models.User = Depends(get_current_user)) -> dict[str, Any]:
    return get_speech_status()


@router.post("/transcribe")
def transcribe_speech(
    payload: SpeechTranscriptionRequest,
    _: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        return transcribe_audio_data_url(
            payload.audio_data_url,
            language=payload.language,
            enable_itn=payload.enable_itn,
        )
    except SpeechRecognitionError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"语音识别失败：{error}") from error


def _resolve_ws_user(token: str | None) -> models.User | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub") or 0)
    except (JWTError, ValueError, TypeError):
        return None

    db = database.SessionLocal()
    try:
        return db.query(models.User).filter(models.User.id == user_id).first()
    finally:
        db.close()


@router.websocket("/realtime")
async def speech_realtime(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    language: str = Query(default="zh"),
):
    user = _resolve_ws_user(token)
    if not user:
        await websocket.close(code=1008, reason="Invalid authentication credentials")
        return
    if not QWEN_ASR_API_KEY:
        await websocket.close(code=1011, reason="DASHSCOPE_API_KEY is not configured")
        return

    await websocket.accept()
    dashscope_headers = {
        "Authorization": f"Bearer {QWEN_ASR_API_KEY}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        async with websockets.connect(
            build_realtime_url(),
            additional_headers=dashscope_headers,
            max_size=8 * 1024 * 1024,
        ) as upstream:
            await upstream.send(json.dumps(build_realtime_session_update(language=language)))
            await websocket.send_json({"type": "ready", **get_speech_status()})

            async def client_to_upstream() -> None:
                while True:
                    try:
                        payload = await websocket.receive_json()
                    except WebSocketDisconnect:
                        await upstream.close()
                        return
                    except Exception:
                        await upstream.close()
                        return

                    message_type = payload.get("type")
                    if message_type == "audio":
                        audio = str(payload.get("audio") or "")
                        if audio:
                            await upstream.send(
                                json.dumps(
                                    {
                                        "type": "input_audio_buffer.append",
                                        "audio": audio,
                                    }
                                )
                            )
                    elif message_type == "commit":
                        await upstream.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    elif message_type == "close":
                        await upstream.send(json.dumps({"type": "session.finish", "event_id": "event_finish"}))
                        await upstream.close()
                        return

            async def upstream_to_client() -> None:
                async for raw_event in upstream:
                    try:
                        event = json.loads(raw_event)
                    except Exception:
                        continue

                    event_type = str(event.get("type") or "")
                    transcript_delta = extract_realtime_transcript_delta(event)
                    transcript = extract_realtime_transcript(event)
                    if transcript_delta:
                        await websocket.send_json(
                            {
                                "type": "transcript_delta",
                                "text": transcript_delta,
                                "model": get_speech_status()["realtime_model"],
                                "event": event_type,
                            }
                        )
                    elif transcript:
                        await websocket.send_json(
                            {
                                "type": "transcript",
                                "text": transcript,
                                "model": get_speech_status()["realtime_model"],
                                "event": event_type,
                            }
                        )
                    elif event_type:
                        await websocket.send_json({"type": "asr_event", "event": event_type})

            await asyncio.gather(client_to_upstream(), upstream_to_client())
    except WebSocketDisconnect:
        return
    except Exception as error:
        try:
            await websocket.send_json({"type": "error", "message": f"实时语音连接失败：{error}"})
        finally:
            await websocket.close(code=1011)
