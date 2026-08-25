import json
import base64
import uuid
import logging
import asyncio
from typing import Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.factory import VoicePipelineFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

# Active session task registry for remote stop/interrupt capability
ACTIVE_SESSIONS: Dict[str, asyncio.Task] = {}


def stop_active_session_turn(session_id: str) -> bool:
    """Utility to cancel/stop an active streaming response turn for a session."""
    task = ACTIVE_SESSIONS.get(session_id)
    if task and not task.done():
        task.cancel()
        logger.info(f"Cancelled active streaming turn for session {session_id}")
        return True
    return False


@router.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    logger.info(f"WebSocket client connected. Session ID: {session_id}")

    # Instantiate pipeline instances using factory
    stt_service = VoicePipelineFactory.create_stt()
    dialogue_service = VoicePipelineFactory.create_dialogue()
    tts_service = VoicePipelineFactory.create_tts()
    vad_service = VoicePipelineFactory.create_vad()

    audio_buffer = bytearray()
    header_bytes = bytearray()
    has_speech_in_buffer = False
    current_turn_task: Optional[asyncio.Task] = None

    async def _cancel_running_turn():
        nonlocal current_turn_task
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
            try:
                await current_turn_task
            except asyncio.CancelledError:
                pass
            current_turn_task = None
            ACTIVE_SESSIONS.pop(session_id, None)

    try:
        # Send session initialization info to client
        await websocket.send_json({"type": "session_init", "session_id": session_id})

        while True:
            # Receive message (binary audio chunk or JSON text control frame)
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            # Handle Binary Audio Stream (Microphone Audio Chunks)
            if "bytes" in message and message["bytes"]:
                chunk_bytes = message["bytes"]
                
                # Capture WebM container header (starts with EBML magic bytes 0x1A 0x45 0xDF 0xA3)
                if chunk_bytes.startswith(b'\x1a\x45\xdf\xa3'):
                    header_bytes = bytearray(chunk_bytes)

                audio_buffer.extend(chunk_bytes)

                # 0. Voice Activity Detection (VAD) Step
                vad_result = vad_service.process_chunk(chunk_bytes)
                if vad_result.is_speech or vad_result.speech_start:
                    has_speech_in_buffer = True

                await websocket.send_json({
                    "type": "vad_status",
                    "is_speech": vad_result.is_speech,
                    "confidence": round(vad_result.confidence, 2),
                    "speech_start": vad_result.speech_start,
                    "speech_end": vad_result.speech_end,
                    "has_buffered_speech": has_speech_in_buffer
                })

                should_trigger_turn = vad_result.speech_end or (len(audio_buffer) > 120000 and not vad_result.is_speech)

                if should_trigger_turn and len(audio_buffer) > 1000:
                    if header_bytes and not audio_buffer.startswith(b'\x1a\x45\xdf\xa3'):
                        buffer_to_process = bytes(header_bytes) + bytes(audio_buffer)
                    else:
                        buffer_to_process = bytes(audio_buffer)

                    audio_buffer.clear()
                    has_speech_in_buffer = False
                    vad_service.reset()

                    logger.info(f"🎙️ VAD Triggered Speech End. Processing {len(buffer_to_process)} bytes audio turn via STT...")

                    try:
                        user_text = await stt_service.transcribe(buffer_to_process, filename="input.webm")
                    except Exception as e:
                        logger.error(f"❌ STT Error: {e}")
                        await websocket.send_json({"type": "error", "message": f"STT Error: {str(e)}"})
                        continue

                    if not user_text.strip():
                        logger.info("ℹ️ STT result was empty or unintelligible.")
                        await websocket.send_json({
                            "type": "stt_result",
                            "text": "[No clear speech detected]"
                        })
                        continue

                    logger.info(f"🗣️ STT Transcribed Text: '{user_text}'")
                    await websocket.send_json({
                        "type": "stt_result",
                        "text": user_text
                    })

                    await _cancel_running_turn()
                    current_turn_task = asyncio.create_task(
                        _process_dialogue_turn(
                            user_text=user_text,
                            session_id=session_id,
                            dialogue_service=dialogue_service,
                            tts_service=tts_service,
                            websocket=websocket
                        )
                    )
                    ACTIVE_SESSIONS[session_id] = current_turn_task

            # Handle Text or JSON Control Frames
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type")

                    if msg_type in ("stop", "interrupt"):
                        logger.info(f"🛑 Received turn stop/interrupt command for session {session_id[:8]}")
                        # Immediately cancel active turn generation & audio synthesis
                        await _cancel_running_turn()
                        audio_buffer.clear()
                        vad_service.reset()
                        await websocket.send_json({
                            "type": "interrupted",
                            "message": "Response streaming stopped by user."
                        })

                    elif msg_type == "text_input":
                        user_text = payload.get("text", "").strip()
                        if user_text:
                            logger.info(f"💬 Received Direct Text Input: '{user_text}'")
                            await _cancel_running_turn()
                            await websocket.send_json({
                                "type": "stt_result",
                                "text": f"[Direct Text]: {user_text}"
                            })
                            current_turn_task = asyncio.create_task(
                                _process_dialogue_turn(
                                    user_text=user_text,
                                    session_id=session_id,
                                    dialogue_service=dialogue_service,
                                    tts_service=tts_service,
                                    websocket=websocket
                                )
                            )
                            ACTIVE_SESSIONS[session_id] = current_turn_task

                    elif msg_type == "audio_turn":
                        b64_data = payload.get("audio_b64", "")
                        if b64_data:
                            audio_bytes = base64.b64decode(b64_data)
                            logger.info(f"🎙️ Received audio turn payload ({len(audio_bytes)} bytes). Transcribing via STT...")
                            audio_buffer.clear()
                            has_speech_in_buffer = False
                            vad_service.reset()

                            try:
                                user_text = await stt_service.transcribe(audio_bytes, filename="recording.webm")
                            except Exception as e:
                                logger.error(f"❌ STT Error on audio turn: {e}")
                                await websocket.send_json({"type": "error", "message": f"STT Error: {str(e)}"})
                                continue

                            if not user_text.strip():
                                logger.info("ℹ️ Audio turn STT output was empty.")
                                await websocket.send_json({
                                    "type": "stt_result",
                                    "text": "[No clear speech detected]"
                                })
                                continue

                            logger.info(f"🗣️ STT Transcribed Text: '{user_text}'")
                            await websocket.send_json({
                                "type": "stt_result",
                                "text": user_text
                            })

                            await _cancel_running_turn()
                            current_turn_task = asyncio.create_task(
                                _process_dialogue_turn(
                                    user_text=user_text,
                                    session_id=session_id,
                                    dialogue_service=dialogue_service,
                                    tts_service=tts_service,
                                    websocket=websocket
                                )
                            )
                            ACTIVE_SESSIONS[session_id] = current_turn_task

                    elif msg_type in ("flush_audio", "audio_end", "speech_end"):
                        if len(audio_buffer) > 500:
                            logger.info(f"⚡ Received '{msg_type}' signal. Flushing {len(audio_buffer)} bytes audio buffer to STT...")
                            if header_bytes and not audio_buffer.startswith(b'\x1a\x45\xdf\xa3'):
                                buffer_to_process = bytes(header_bytes) + bytes(audio_buffer)
                            else:
                                buffer_to_process = bytes(audio_buffer)

                            audio_buffer.clear()
                            has_speech_in_buffer = False
                            vad_service.reset()

                            try:
                                user_text = await stt_service.transcribe(buffer_to_process, filename="input.webm")
                            except Exception as e:
                                logger.error(f"❌ STT Error on flush: {e}")
                                await websocket.send_json({"type": "error", "message": f"STT Error: {str(e)}"})
                                continue

                            if not user_text.strip():
                                logger.info("ℹ️ Flushed STT result was empty or unintelligible.")
                                await websocket.send_json({
                                    "type": "stt_result",
                                    "text": "[No clear speech detected]"
                                })
                                continue

                            logger.info(f"🗣️ Flushed STT Transcribed Text: '{user_text}'")
                            await websocket.send_json({
                                "type": "stt_result",
                                "text": user_text
                            })

                            await _cancel_running_turn()
                            current_turn_task = asyncio.create_task(
                                _process_dialogue_turn(
                                    user_text=user_text,
                                    session_id=session_id,
                                    dialogue_service=dialogue_service,
                                    tts_service=tts_service,
                                    websocket=websocket
                                )
                            )
                            ACTIVE_SESSIONS[session_id] = current_turn_task
                        else:
                            logger.info("ℹ️ Received flush_audio signal, but audio_buffer is empty.")

                    elif msg_type == "reset":
                        await _cancel_running_turn()
                        audio_buffer.clear()
                        vad_service.reset()
                        dialogue_service.reset_session(session_id)
                        await websocket.send_json({
                            "type": "info",
                            "message": "Session history & VAD buffers reset."
                        })

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                except json.JSONDecodeError:
                    raw_text = message["text"].strip()
                    if raw_text:
                        await _cancel_running_turn()
                        await websocket.send_json({
                            "type": "stt_result",
                            "text": f"[Text Input]: {raw_text}"
                        })
                        current_turn_task = asyncio.create_task(
                            _process_dialogue_turn(
                                user_text=raw_text,
                                session_id=session_id,
                                dialogue_service=dialogue_service,
                                tts_service=tts_service,
                                websocket=websocket
                            )
                        )
                        ACTIVE_SESSIONS[session_id] = current_turn_task

    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"WebSocket client disconnected. Session ID: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}", exc_info=True)
    finally:
        await _cancel_running_turn()
        ACTIVE_SESSIONS.pop(session_id, None)


async def _process_dialogue_turn(
    user_text: str,
    session_id: str,
    dialogue_service,
    tts_service,
    websocket: WebSocket
):
    """
    Orchestrates streaming turn execution with cancellation support.
    """
    sentence_buffer = ""
    current_agent_name = "Agent"
    has_started_audio = False

    try:
        # Stream dialogue response from Multi-Agent system
        async for chunk in dialogue_service.process(user_text, session_id):
            
            # Send supervisor thought frame
            if chunk.thought:
                await websocket.send_json({
                    "type": "agent_thought",
                    "agent": chunk.agent_name,
                    "thought": chunk.thought
                })
                continue

            current_agent_name = chunk.agent_name

            # Send text token chunk to frontend instantly
            await websocket.send_json({
                "type": "agent_chunk",
                "agent": chunk.agent_name,
                "role": chunk.agent_role,
                "text": chunk.text,
                "is_final": chunk.is_final
            })

            if chunk.text:
                sentence_buffer += chunk.text
                # Stream TTS chunk as soon as punctuation/sentence boundary is reached
                if any(p in sentence_buffer for p in [".", "!", "?", "\n", ";"]):
                    text_to_speak = sentence_buffer.strip()
                    if text_to_speak:
                        has_started_audio = await _synthesize_and_send_audio_chunk(
                            text=text_to_speak,
                            agent_name=current_agent_name,
                            tts_service=tts_service,
                            websocket=websocket,
                            has_started_audio=has_started_audio
                        )
                    sentence_buffer = ""

        # Flush remaining text in sentence buffer
        if sentence_buffer.strip():
            has_started_audio = await _synthesize_and_send_audio_chunk(
                text=sentence_buffer.strip(),
                agent_name=current_agent_name,
                tts_service=tts_service,
                websocket=websocket,
                has_started_audio=has_started_audio
            )

        if has_started_audio:
            await websocket.send_json({"type": "audio_end"})

    except asyncio.CancelledError:
        logger.info(f"Turn execution cancelled for session {session_id}")
        raise


async def _synthesize_and_send_audio_chunk(
    text: str,
    agent_name: str,
    tts_service,
    websocket: WebSocket,
    has_started_audio: bool
) -> bool:
    """Helper to synthesize audio sentence chunk and send binary audio to WebSocket client."""
    if not has_started_audio:
        await websocket.send_json({"type": "audio_start", "agent": agent_name})
        has_started_audio = True

    try:
        audio_bytes = await tts_service.synthesize(text)
        if audio_bytes:
            b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
            await websocket.send_json({
                "type": "audio_chunk",
                "audio_b64": b64_audio,
                "mime": "audio/mp3"
            })
    except Exception as e:
        logger.error(f"Streaming TTS error for text '{text[:20]}...': {e}")
    
    return has_started_audio
