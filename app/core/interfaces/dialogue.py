from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from pydantic import BaseModel, Field


class DialogueChunk(BaseModel):
    agent_name: str = Field(..., description="Name of the active agent producing this chunk")
    agent_role: str = Field(..., description="Role/description of the agent")
    text: str = Field(..., description="Text segment produced by the agent")
    is_final: bool = Field(False, description="Whether this is the final chunk of the response turn")
    thought: Optional[str] = Field(None, description="Optional reasoning/routing log from supervisor")


class BaseDialogueEngine(ABC):
    """Abstract Base Class for Multi-Agent Dialogue Engines."""

    @abstractmethod
    async def process(
        self,
        user_input: str,
        session_id: str
    ) -> AsyncGenerator[DialogueChunk, None]:
        """
        Process user speech transcription and yield response chunks.
        
        :param user_input: Transcribed text from user.
        :param session_id: Session identifier for context tracking.
        :return: Async generator of DialogueChunk objects.
        """
        pass

    @abstractmethod
    def reset_session(self, session_id: str) -> None:
        """Reset conversation history for a given session."""
        pass
