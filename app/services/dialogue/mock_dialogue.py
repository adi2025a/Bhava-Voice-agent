import asyncio
import random
from typing import AsyncGenerator, Dict, List
from app.core.interfaces.dialogue import BaseDialogueEngine, DialogueChunk


class MockDialogueEngine(BaseDialogueEngine):
    """
    Mock Multi-Agent dialogue engine for zero-dependency testing.
    Simulates supervisor routing to specialized worker agents.
    """

    AGENT_PROFILES = [
        {
            "name": "Code Specialist",
            "role": "Technical expert on software, Python, and web architectures.",
            "responses": [
                "That's a great question about software architecture! In Python, using FastAPI with WebSockets provides low-latency bi-directional streaming ideal for voice pipelines.",
                "To optimize live audio streaming, you can process raw PCM chunks in small buffers of 100 to 200 milliseconds to minimize latency."
            ]
        },
        {
            "name": "Creative Storyteller",
            "role": "Imaginative roleplay and creative assistant.",
            "responses": [
                "Imagine a distant galaxy where AI neural networks communicate through vibrant streams of light across cosmic space!",
                "Once upon a time in a bustling digital city, multiple agent bots worked in harmony to translate human speech into instant thoughts."
            ]
        },
        {
            "name": "Voice Concierge",
            "role": "General friendly voice assistant.",
            "responses": [
                "Hello! I'm your multi-agent voice assistant. I can help answer questions, write code, or just chat with you.",
                "I've routed your query to our specialized agents. Everything is operating smoothly!"
            ]
        }
    ]

    def __init__(self):
        self.session_memories: Dict[str, List[dict]] = {}

    def reset_session(self, session_id: str) -> None:
        self.session_memories.pop(session_id, None)

    async def process(
        self,
        user_input: str,
        session_id: str
    ) -> AsyncGenerator[DialogueChunk, None]:
        # Step 1: Supervisor thought chunk
        agent = random.choice(self.AGENT_PROFILES)
        supervisor_thought = f"Supervisor: Analyzed user query '{user_input}'. Routing turn to {agent['name']} ({agent['role']})."

        yield DialogueChunk(
            agent_name="Supervisor Router",
            agent_role="Intelligent intent classification & multi-agent routing",
            text="",
            is_final=False,
            thought=supervisor_thought
        )
        await asyncio.sleep(0.3)

        # Step 2: Selected Agent streams answer text in fragments
        full_response = random.choice(agent["responses"])
        words = full_response.split(" ")

        for i, word in enumerate(words):
            chunk_text = word + (" " if i < len(words) - 1 else "")
            is_final = (i == len(words) - 1)
            yield DialogueChunk(
                agent_name=agent["name"],
                agent_role=agent["role"],
                text=chunk_text,
                is_final=is_final
            )
            await asyncio.sleep(0.08)
