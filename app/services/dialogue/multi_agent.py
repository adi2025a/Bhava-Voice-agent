import logging
import json
from typing import AsyncGenerator, Dict, List, Optional
from groq import AsyncGroq
from app.core.interfaces.dialogue import BaseDialogueEngine, DialogueChunk
from app.services.dialogue.mock_dialogue import MockDialogueEngine

logger = logging.getLogger(__name__)


AGENTS_CONFIG = {
    "Code Specialist": {
        "role": "Software Engineering & Architecture Expert",
        "system_prompt": (
            "You are the Code Specialist agent in a multi-agent voice system. "
            "Provide concise, precise, and practical answers for software development, debugging, "
            "and architecture. Keep formatting clean and easy to listen to in voice TTS."
        )
    },
    "Creative Storyteller": {
        "role": "Creative Assistant & Imaginative Persona",
        "system_prompt": (
            "You are the Creative Storyteller agent. Respond with warmth, vivid descriptions, "
            "engaging tone, and creative flair suitable for spoken voice response."
        )
    },
    "Science & Knowledge Expert": {
        "role": "Factual & Scientific Research Expert",
        "system_prompt": (
            "You are the Science & Knowledge Expert agent. Deliver accurate, clear, "
            "and fascinating explanations of scientific facts, history, and concepts."
        )
    },
    "General Assistant": {
        "role": "Friendly Conversational Assistant",
        "system_prompt": (
            "You are the General Voice Assistant agent. Be helpful, concise, conversational, "
            "and friendly. Optimise your output for spoken dialogue."
        )
    }
}


class MultiAgentEngine(BaseDialogueEngine):
    """
    Multi-Agent Dialogue Engine using Supervisor-Worker orchestration pattern.
    Supports Groq LLMs (Llama 3.3 70B / Mixtral) with streaming.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = AsyncGroq(api_key=api_key) if api_key else None
        self.sessions: Dict[str, List[dict]] = {}
        self.fallback_engine = MockDialogueEngine()

    def reset_session(self, session_id: str) -> None:
        self.sessions.pop(session_id, None)

    async def _route_agent(self, user_input: str, history: List[dict]) -> tuple[str, str]:
        """Supervisor router step: decides which specialized agent should respond."""
        if not self.client:
            return "General Assistant", "Mock routing due to missing API key."

        routing_prompt = f"""You are the Supervisor Router for a multi-agent AI system.
Available agents:
1. "Code Specialist": Software, coding, bugs, APIs, tech stack, algorithms.
2. "Creative Storyteller": Creative writing, stories, roleplay, poems, fun brainstorming.
3. "Science & Knowledge Expert": Facts, science, math, history, definitions, explainers.
4. "General Assistant": Greetings, casual chit-chat, ambiguous queries, general help.

User Input: "{user_input}"

Respond ONLY with a JSON object in this exact format:
{{"selected_agent": "<agent_name>", "reasoning": "<short sentence explaining why>"}}"""

        try:
            res = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": routing_prompt}],
                temperature=0.1,
                max_tokens=150,
                response_format={"type": "json_object"}
            )
            content = res.choices[0].message.content or "{}"
            data = json.loads(content)
            selected = data.get("selected_agent", "General Assistant")
            reasoning = data.get("reasoning", "Routed based on user intent.")
            
            if selected not in AGENTS_CONFIG:
                selected = "General Assistant"
                
            return selected, reasoning
        except Exception as e:
            logger.warning(f"Routing LLM error, falling back to General Assistant: {e}")
            return "General Assistant", f"Fallback routing: {str(e)}"

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

        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
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

        except Exception as e:
            logger.error(f"MultiAgent dialogue execution error: {e}", exc_info=True)
            # Yield fallback from Mock Dialogue Engine if error occurs mid-way
            async for chunk in self.fallback_engine.process(user_input, session_id):
                yield chunk
