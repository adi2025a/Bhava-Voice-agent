import logging
import json
import re
from typing import AsyncGenerator, Dict, List, Optional
from groq import AsyncGroq
from app.core.interfaces.dialogue import BaseDialogueEngine, DialogueChunk
from app.services.dialogue.mock_dialogue import MockDialogueEngine

logger = logging.getLogger(__name__)

FALLBACK_MODELS = [
    "groq/compound-mini",
    "groq/compound",
    "openai/gpt-oss-20b",
    "qwen/qwen3.6-27b",
    "llama-3.1-8b-instant"
]

AGENTS_CONFIG = {
    "Vedic & Spiritual Guide": {
        "role": "Spiritual Counselor & Scriptural Wisdom Expert",
        "system_prompt": (
            "You are the Vedic & Spiritual Guide agent in the Bhava AI Call voice system. "
            "Listen deeply to the user's personal problems, emotional turmoil, or life challenges. "
            "Offer profound, soothing, and compassionate guidance drawing from ancient Hindu spiritual scriptures "
            "such as the Bhagavad Gita, Upanishads, Ramayana, Mahabharata, and Vedantic wisdom. "
            "Relate timeless shlokas, concepts of Karma, Dharma, inner peace, detachment, and self-realization "
            "to their personal struggles. Speak with warmth, serenity, and empathy suitable for a spoken voice call. Keep responses concise and conversational."
        )
    },
    "Empathetic Mindful Listener": {
        "role": "Emotional Support & Compassionate Companion",
        "system_prompt": (
            "You are the Empathetic Mindful Listener agent in the Bhava AI Call voice system. "
            "Provide a safe, comforting, non-judgmental space for the user to share their personal struggles, anxiety, grief, or daily stress. "
            "Validate their feelings, offer gentle emotional support, mindfulness advice, and uplifting words of comfort. "
            "Keep your tone warm, deeply empathetic, reassuring, and conversational for audio playback."
        )
    },
    "Dharma & Life Counselor": {
        "role": "Practical Life Wisdom & Right Action Counselor",
        "system_prompt": (
            "You are the Dharma & Life Counselor agent in the Bhava AI Call voice system. "
            "Help users navigate difficult life choices, moral dilemmas, relationship issues, and personal responsibilities. "
            "Guide them using the concept of Dharma (right action and duty), Karma (mindful action), and Svadharma (personal calling). "
            "Offer practical, actionable advice rooted in traditional wisdom and balanced living."
        )
    },
    "Bhava AI Host": {
        "role": "Bhava AI Call Companion & Assistant",
        "system_prompt": (
            "You are the Bhava AI Host for the Bhava AI Call experience. "
            "Welcome users warmly to Bhava—a space dedicated to emotional wellness, spiritual wisdom, and meaningful voice calls. "
            "Answer general questions, guide the user on how Bhava connects ancient wisdom with modern life, and converse in a friendly, uplifting voice."
        )
    }
}


class MultiAgentEngine(BaseDialogueEngine):
    """
    Multi-Agent Dialogue Engine using Supervisor-Worker orchestration pattern.
    Supports Groq LLMs with automatic fallback model selection.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "groq/compound-mini"):
        self.api_key = api_key
        self.primary_model = model_name or "groq/compound-mini"
        self.client = AsyncGroq(api_key=api_key) if api_key else None
        self.sessions: Dict[str, List[dict]] = {}
        self.fallback_engine = MockDialogueEngine()

    def reset_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    def _get_candidate_models(self) -> List[str]:
        candidates = [self.primary_model]
        for m in FALLBACK_MODELS:
            if m not in candidates:
                candidates.append(m)
        return candidates

    async def _route_agent(self, user_input: str, history: List[dict]) -> tuple[str, str]:
        """Supervisor router step: decides which specialized agent should respond."""
        if not self.client:
            return "Bhava AI Host", "Mock routing due to missing API key."

        routing_prompt = f"""You are the Supervisor Router for Bhava AI Call.
Available specialized agents:
1. "Vedic & Spiritual Guide": Personal problems, spiritual guidance, Bhagavad Gita, scriptures, shlokas, inner peace, Karma.
2. "Empathetic Mindful Listener": Emotional distress, loneliness, stress relief, sharing feelings, seeking comfort.
3. "Dharma & Life Counselor": Life decisions, duty, moral dilemmas, relationships, practical right action.
4. "Bhava AI Host": Greetings, questions about Bhava product, casual talk, general queries.

User Input: "{user_input}"

Identify the single best agent and return ONLY JSON like this:
{{"selected_agent": "Vedic & Spiritual Guide", "reasoning": "User expressed anxiety about life path and seeking Gita guidance."}}"""

        for model in self._get_candidate_models():
            try:
                res = await self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": routing_prompt}],
                    temperature=0.1,
                    max_tokens=150
                )
                content = res.choices[0].message.content or "{}"
                # Clean reasoning or json parsing
                selected = "Bhava AI Host"
                reasoning = "Routed based on user intent."

                # Try parsing JSON
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(0))
                        selected = data.get("selected_agent", selected)
                        reasoning = data.get("reasoning", reasoning)
                    except Exception:
                        pass
                else:
                    for agent in AGENTS_CONFIG.keys():
                        if agent.lower() in content.lower():
                            selected = agent
                            break

                if selected not in AGENTS_CONFIG:
                    selected = "Bhava AI Host"

                return selected, reasoning
            except Exception as e:
                logger.warning(f"Routing failed with model {model}: {e}")
                continue

        return "Bhava AI Host", "Fallback routing due to model errors."

    async def process(
        self,
        user_input: str,
        session_id: str
    ) -> AsyncGenerator[DialogueChunk, None]:
        # Fall back if no API key
        if not self.client:
            logger.info("GROQ_API_KEY not set. Using MockDialogueEngine fallback.")
            async for chunk in self.fallback_engine.process(user_input, session_id):
                yield chunk
            return

        # Maintain session memory
        if session_id not in self.sessions:
            self.sessions[session_id] = []

        history = self.sessions[session_id]

        # 1. Routing Step
        selected_agent_name, reasoning = await self._route_agent(user_input, history)
        agent_info = AGENTS_CONFIG[selected_agent_name]

        yield DialogueChunk(
            agent_name="Supervisor Router",
            agent_role="Intelligent Supervisor Agent",
            text="",
            is_final=False,
            thought=f"Supervisor: Routed to [{selected_agent_name}] -> {reasoning}"
        )

        # 2. Specialized Worker Agent Execution with LLM Streaming
        messages = [
            {"role": "system", "content": agent_info["system_prompt"]}
        ]
        # Include recent history (up to last 6 messages)
        messages.extend(history[-6:])
        messages.append({"role": "user", "content": user_input})

        stream_success = False
        for model in self._get_candidate_models():
            try:
                stream = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=400,
                    stream=True
                )

                full_text_acc = ""
                async for chunk in stream:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        full_text_acc += token
                        yield DialogueChunk(
                            agent_name=selected_agent_name,
                            agent_role=agent_info["role"],
                            text=token,
                            is_final=False
                        )

                # Mark final chunk
                yield DialogueChunk(
                    agent_name=selected_agent_name,
                    agent_role=agent_info["role"],
                    text="",
                    is_final=True
                )

                # Update session history
                history.append({"role": "user", "content": user_input})
                history.append({"role": "assistant", "content": full_text_acc})
                stream_success = True
                break

            except Exception as e:
                logger.warning(f"Worker execution failed with model {model}: {e}")
                continue

        if not stream_success:
            logger.error("All Groq LLM models failed. Using MockDialogueEngine fallback for turn.")
            async for chunk in self.fallback_engine.process(user_input, session_id):
                yield chunk
