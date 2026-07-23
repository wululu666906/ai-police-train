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
    SpeechRecognitionError,
    build_realtime_session_update,
    build_realtime_url,
    extract_realtime_transcript,
    extract_realtime_transcript_delta,
    get_qwen_asr_api_key,
    get_qwen_realtime_asr_proxy,
    get_speech_status,
    transcribe_audio_data_url,
)
from services.qwen_config import qwen_default_headers

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
    current_user: models.User = Depends(get_current_user),
) -> dict[str, Any]:
    db = database.SessionLocal()
    try:
        result = transcribe_audio_data_url(
            payload.audio_data_url,
            language=payload.language,
            enable_itn=payload.enable_itn,
        )
        db.add(models.SpeechUsageLog(
            user_id=current_user.id,
            mode="transcribe",
            status="success",
            language=payload.language,
            model=str(result.get("model") or ""),
            text_length=len(str(result.get("text") or result.get("transcript") or "")),
        ))
        db.commit()
        return result
    except SpeechRecognitionError as error:
        db.add(models.SpeechUsageLog(
            user_id=current_user.id,
            mode="transcribe",
            status="failed",
            language=payload.language,
            error_message=str(error),
        ))
        db.commit()
        raise HTTPException(status_code=400, detail=f"语音识别失败：{error}") from error
    except Exception as error:
        db.add(models.SpeechUsageLog(
            user_id=current_user.id,
            mode="transcribe",
            status="failed",
            language=payload.language,
            error_message=str(error),
        ))
        db.commit()
        raise HTTPException(status_code=502, detail=f"语音识别失败：{error}") from error
    finally:
        db.close()


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
        await websocket.close(code=1008, reason="登录凭证无效")
        return
    qwen_asr_api_key = get_qwen_asr_api_key()
    if not qwen_asr_api_key:
        await websocket.close(code=1011, reason="语音识别服务未配置")
        return

    await websocket.accept()
    speech_log_id = None
    db = database.SessionLocal()
    try:
        status_payload = get_speech_status()
        log = models.SpeechUsageLog(
            user_id=user.id,
            mode="realtime",
            status="connected",
            language=language,
            model=str(status_payload.get("realtime_model") or ""),
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        speech_log_id = log.id
    finally:
        db.close()
    dashscope_headers = {
        "Authorization": f"Bearer {qwen_asr_api_key}",
        "OpenAI-Beta": "realtime=v1",
    }
    dashscope_headers.update(qwen_default_headers(str(status_payload.get("realtime_url") or "")))

    try:
        async with websockets.connect(
            build_realtime_url(),
            additional_headers=dashscope_headers,
            proxy=get_qwen_realtime_asr_proxy(),
            open_timeout=15,
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
            if speech_log_id:
                db = database.SessionLocal()
                try:
                    log = db.query(models.SpeechUsageLog).filter(models.SpeechUsageLog.id == speech_log_id).first()
                    if log:
                        log.status = "success"
                        db.add(log)
                        db.commit()
                finally:
                    db.close()
    except WebSocketDisconnect:
        return
    except Exception as error:
        if speech_log_id:
            db = database.SessionLocal()
            try:
                log = db.query(models.SpeechUsageLog).filter(models.SpeechUsageLog.id == speech_log_id).first()
                if log:
                    log.status = "failed"
                    log.error_message = str(error)
                    db.add(log)
                    db.commit()
            finally:
                db.close()
        error_text = str(error)
        if isinstance(error, PermissionError) or "WinError 5" in error_text:
            error_text = "实时语音上游连接被本机/网络拒绝，请检查 QWEN_REALTIME_ASR_URL 是否可达"
        elif "Name or service not known" in error_text or "Temporary failure in name resolution" in error_text:
            error_text = "实时语音上游域名无法解析，请检查 QWEN_REALTIME_ASR_URL"
        elif "Connection refused" in error_text or "timed out" in error_text.lower():
            error_text = "实时语音上游不可达，请检查网络、代理和 QWEN_REALTIME_ASR_URL"
        try:
            await websocket.send_json({"type": "error", "message": f"实时语音连接失败：{error_text}"})
        finally:
            await websocket.close(code=1011)
