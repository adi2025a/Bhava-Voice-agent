import json
import base64
import uuid
import logging
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.factory import VoicePipelineFactory

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session_id = str(uuid.uuid4())
    logger.info(f"WebSocket client connected. Session ID: {session_id}")

    # Instantiate pipeline instances using factory
    stt_service = VoicePipelineFactory.create_stt()
    dialogue_service = VoicePipelineFactory.create_dialogue()
    tts_service = VoicePipelineFactory.create_tts()

    try:
        while True:
            # Receive message (binary audio or JSON text control frame)
            message = await websocket.receive()

            # Handle Binary Audio Stream (Microphone Audio Buffer)
            if "bytes" in message and message["bytes"]:
                audio_bytes = message["bytes"]
                
                # 1. Speech-To-Text Step
                try:
                    user_text = await stt_service.transcribe(audio_bytes, filename="input.webm")
                except Exception as e:
                    logger.error(f"STT Error: {e}")
                    await websocket.send_json({"type": "error", "message": f"STT Error: {str(e)}"})
                    continue

                if not user_text.strip():
                    await websocket.send_json({
                        "type": "stt_result",
                        "text": "[No clear speech detected]"
                    })
                    continue

                # Notify client of recognized text
                await websocket.send_json({
                    "type": "stt_result",
                    "text": user_text
                })

                # Process turn through Dialogue and TTS
                await _process_dialogue_turn(
                    user_text=user_text,
                    session_id=session_id,
                    dialogue_service=dialogue_service,
                    tts_service=tts_service,
                    websocket=websocket
                )

            # Handle Text or JSON Control Frames
            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    msg_type = payload.get("type")

                    if msg_type == "text_input":
                        user_text = payload.get("text", "").strip()
                        if user_text:
                            await websocket.send_json({
                                "type": "stt_result",
                                "text": f"[Direct Text]: {user_text}"
                            })
                            await _process_dialogue_turn(
                                user_text=user_text,
                                session_id=session_id,
                                dialogue_service=dialogue_service,
                                tts_service=tts_service,
                                websocket=websocket
                            )

                    elif msg_type == "reset":
                        dialogue_service.reset_session(session_id)
                        await websocket.send_json({
                            "type": "info",
                            "message": "Session history reset successfully."
                        })

                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})

                except json.JSONDecodeError:
                    # Treat raw text string as direct text input query
                    raw_text = message["text"].strip()
                    if raw_text:
                        await websocket.send_json({
                            "type": "stt_result",
                            "text": f"[Text Input]: {raw_text}"
                        })
                        await _process_dialogue_turn(
                            user_text=raw_text,
                            session_id=session_id,
                            dialogue_service=dialogue_service,
                            tts_service=tts_service,
                            websocket=websocket
                        )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected. Session ID: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error in session {session_id}: {e}", exc_info=True)


async def _process_dialogue_turn(
    user_text: str,
    session_id: str,
    dialogue_service,
    tts_service,
    websocket: WebSocket
):
    """Orchestrates Dialogue generation and streaming TTS audio response back over WebSocket."""
    
    # Text accumulator for TTS synthesis
    accumulated_agent_text = ""
    current_agent_name = "Agent"

    # Stream dialogue response from Multi-Agent system
    async for chunk in dialogue_service.process(user_text, session_id):
        
        # If supervisor thought frame
        if chunk.thought:
            await websocket.send_json({
                "type": "agent_thought",
                "agent": chunk.agent_name,
                "thought": chunk.thought
            })
            continue

        current_agent_name = chunk.agent_name

        # Send text chunk to frontend
        await websocket.send_json({
            "type": "agent_chunk",
            "agent": chunk.agent_name,
            "role": chunk.agent_role,
            "text": chunk.text,
            "is_final": chunk.is_final
        })

        if chunk.text:
            accumulated_agent_text += chunk.text

    # Synthesize & Stream TTS Audio
    if accumulated_agent_text.strip():
        await websocket.send_json({"type": "audio_start", "agent": current_agent_name})
        try:
            audio_bytes = await tts_service.synthesize(accumulated_agent_text)
            if audio_bytes:
                b64_audio = base64.b64encode(audio_bytes).decode("utf-8")
                await websocket.send_json({
                    "type": "audio_chunk",
                    "audio_b64": b64_audio,
                    "mime": "audio/mp3"
                })
        except Exception as e:
            logger.error(f"TTS Error: {e}", exc_info=True)
            await websocket.send_json({"type": "error", "message": f"TTS Synthesis Error: {str(e)}"})
        finally:
            await websocket.send_json({"type": "audio_end"})
