from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class BaseTTS(ABC):
    """Abstract Base Class for Text-To-Speech services."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: Optional[str] = None
    ) -> bytes:
        """
        Synthesize entire text block into binary audio bytes (MP3/WAV/OGG).
        
        :param text: Text to synthesize.
        :param voice: Voice name/identifier.
        :return: Binary audio content.
        """
        pass

    @abstractmethod
    async def synthesize_stream(
        self,
        text_generator: AsyncGenerator[str, None],
        voice: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream synthesized audio chunks as text chunks arrive.
        
        :param text_generator: Async generator yielding text fragments.
        :param voice: Voice name/identifier.
        :return: Async generator of binary audio chunks.
        """
        pass
