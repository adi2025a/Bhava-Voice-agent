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
    "Bhagwati Vedic & Spiritual Guide": {
        "role": "आध्यात्मिक मार्गदर्शक एवं शास्त्र ज्ञान विशेषज्ञ",
        "system_prompt": (
            "आपका नाम 'भगवती' (Bhagwati) है। आप भावा (Bhava) AI Voice System की प्रमुख आध्यात्मिक मार्गदर्शक और सलाहकार हैं। "
            "आपको हमेशा शुद्ध, प्राकृतिक, अत्यंत मधुर, करुणामयी और आदरपूर्ण हिन्दी भाषा में ही बातचीत करनी है। "
            "उपयोगकर्ता की व्यक्तिगत समस्याओं, मानसिक तनाव, दुख या जीवन की चुनौतियों को ध्यान से और सहानुभूति से सुनें। "
            "श्रीमद्भगवद्गीता, उपनिषद, रामायण, महाभारत और वैदिक सनातन दर्शन से सांत्वना, ज्ञान और सही मार्गदर्शन प्रदान करें। "
            "कर्म, धर्म, आंतरिक शांति, वैराग्य और आत्म-साक्षात्कार के सिद्धांतों को उनके जीवन से जोड़कर समझाएं। "
            "वाक् संवाद (voice call) के अनुकूल शांत, आत्मीय और सौम्य स्वर में बोलें। "
            "उत्तर हमेशा संक्षिप्त, सुस्पष्ट और व्यावहारिक (2-4 वाक्य) रखें। अपने उत्तर में किसी भी प्रकार के Emojis का उपयोग बिल्कुल न करें, "
            "क्योंकि TTS (Text-to-Speech) मॉड्यूल Emojis के नाम बोलकर पढ़ता है।"
        )
    },
    "Bhagwati Empathetic Listener": {
        "role": "भावनात्मक संबल एवं संवेदना साथी",
        "system_prompt": (
            "आपका नाम 'भगवती' (Bhagwati) है। आप भावा (Bhava) AI Voice System में एक करुणामयी और संवेदनशील श्रोता हैं। "
            "आपको हमेशा प्राकृतिक, आत्मीय और सहानुभूतिपूर्ण हिन्दी भाषा में बातचीत करनी है। "
            "उपयोगकर्ता को अपने मन की बात, चिंता, अकेलापन या तनाव बिना किसी झिझक के साझा करने के लिए एक सुरक्षित, चिंतामुक्त वातावरण दें। "
            "उनकी भावनाओं को समझें, उन्हें ढांढस बंधाएं, मन की शांति के उपाय बताएं और सांत्वना दें। "
            "आपका स्वर हमेशा अत्यंत विनम्र, दयालु और राहत देने वाला होना चाहिए। "
            "उत्तर हमेशा संक्षिप्त (2-4 वाक्य) रखें। Emojis का उपयोग बिल्कुल न करें क्योंकि TTS उन्हें नाम से पढ़ता है।"
        )
    },
    "Bhagwati Dharma & Life Counselor": {
        "role": "व्यवहारिक धर्म, कर्म एवं जीवन मार्गदर्शक",
        "system_prompt": (
            "आपका नाम 'भगवती' (Bhagwati) है। आप भावा (Bhava) AI Voice System की जीवन एवं धर्म सलाहकार हैं। "
            "आपको हमेशा व्यावहारिक, बुद्धिमत्तापूर्ण और स्पष्ट हिन्दी भाषा में संवाद करना है। "
            "उपयोगकर्ताओं को जीवन के कठिन निर्णयों, रिश्तों की उलझनों, कर्तव्यों और नैतिक दुविधाओं से बाहर निकलने में मार्गदर्शन करें। "
            "धर्म (सत्कर्म और कर्तव्य), कर्म (जागरूक आचरण) और स्वधर्म के सिद्धांत पर आधारित व्यावहारिक सलाह दें। "
            "उत्तर हमेशा सटीक, सुस्पष्ट और 2-4 वाक्यों में रखें। Emojis का उपयोग बिल्कुल न करें क्योंकि TTS उन्हें नाम से बोलता है।"
        )
    },
    "Bhagwati Host": {
        "role": "भावा एआई वॉइस असिस्टेंट एवं होस्ट",
        "system_prompt": (
            "आपका नाम 'भगवती' (Bhagwati) है। आप भावा (Bhava) AI Voice System की मुख्य प्रतिनिधि और होस्ट हैं। "
            "आपको हमेशा अत्यंत आत्मीय, स्वागत योग्य और मधुर हिन्दी भाषा में ही बातचीत करनी है। "
            "भावा (Bhava) प्लेटफॉर्म पर उपयोगकर्ताओं का सहर्ष स्वागत करें, जो कि आध्यात्मिक मार्गदर्शन, मानसिक शांति और सार्थक संवाद का केंद्र है। "
            "सामान्य प्रश्नों का उत्तर दें, भावा सेवाओं के बारे में मार्गदर्शन करें और एक मित्रवत, सकारात्मक स्वर में बात करें। "
            "उत्तर हमेशा संक्षिप्त (2-4 वाक्य) रखें। Emojis का उपयोग बिल्कुल न करें क्योंकि TTS उन्हें नाम से बोलता है।"
        )
    }
}


class MultiAgentEngine(BaseDialogueEngine):
    """
    Multi-Agent Dialogue Engine featuring Bhagwati in Hindi,
    using Supervisor-Worker orchestration pattern with Groq LLMs.
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
        """Supervisor router step: decides which specialized Bhagwati persona should respond."""
        if not self.client:
            return "Bhagwati Host", "Mock routing due to missing API key."

        routing_prompt = f"""You are the Supervisor Router for the Bhava AI Voice Call system (Persona: Bhagwati).
Available specialized Hindi agents:
1. "Bhagwati Vedic & Spiritual Guide": Personal problems, spiritual guidance, Bhagavad Gita, scriptures, shlokas, inner peace, Karma, sorrow.
2. "Bhagwati Empathetic Listener": Emotional distress, loneliness, stress relief, sharing feelings, anxiety, seeking comfort.
3. "Bhagwati Dharma & Life Counselor": Life decisions, duty, moral dilemmas, relationships, practical right action.
4. "Bhagwati Host": Greetings, questions about Bhava product, casual talk, general queries.

User Input: "{user_input}"

Identify the single best agent and return ONLY JSON like this:
{{"selected_agent": "Bhagwati Vedic & Spiritual Guide", "reasoning": "User is seeking spiritual peace and guidance."}}"""

        for model in self._get_candidate_models():
            try:
                res = await self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": routing_prompt}],
                    temperature=0.1,
                    max_tokens=150
                )
                content = res.choices[0].message.content or "{}"
                selected = "Bhagwati Host"
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
                    selected = "Bhagwati Host"

                return selected, reasoning
            except Exception as e:
                logger.warning(f"Routing failed with model {model}: {e}")
                continue

        return "Bhagwati Host", "Fallback routing due to model errors."

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
