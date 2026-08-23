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
            "name": "Vedic & Spiritual Guide",
            "role": "Spiritual Counselor & Scriptural Wisdom Expert",
            "responses": [
                "In the Bhagavad Gita, Lord Krishna teaches us that we have a right to perform our duty, but never to the fruits of our actions. Focus on your effort with a peaceful heart.",
                "Whenever life feels overwhelming, remember that the true self, the Atman, remains untouched by temporary storms. Take a deep breath and center your mind."
            ]
        },
        {
            "name": "Empathetic Mindful Listener",
            "role": "Emotional Support & Compassionate Companion",
            "responses": [
                "I hear you, and your feelings are completely valid. It takes courage to open up about personal struggles. I'm right here listening.",
                "Take this moment to pause. Whatever you are going through, remember that peace begins with self-compassion and gentle self-care."
            ]
        },
        {
            "name": "Dharma & Life Counselor",
            "role": "Practical Life Wisdom & Right Action Counselor",
            "responses": [
                "When facing difficult choices, ask yourself which path aligns with your true Dharma—your duty to yourself, your family, and truth.",
                "Karma teaches us that every mindful action plants a seed of future harmony. Choose clarity over reaction."
            ]
        },
        {
            "name": "Bhava AI Host",
            "role": "Bhava AI Call Companion & Assistant",
            "responses": [
                "Welcome to Bhava AI Call! I am here to help you connect with timeless spiritual wisdom and compassionate listening.",
                "Feel free to share what is on your mind or ask any question. Our specialized guides are ready to support you."
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
