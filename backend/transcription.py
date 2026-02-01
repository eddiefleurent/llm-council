"""Audio transcription using Groq's Whisper API."""

import os
import logging

logger = logging.getLogger(__name__)

# Lazy-loaded Groq client
_client = None


class GroqNotConfiguredError(Exception):
    """Raised when GROQ_API_KEY is not configured."""
    pass


def get_groq_client():
    """Get or create the Groq client. Raises GroqNotConfiguredError if not configured."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise GroqNotConfiguredError(
                "Voice transcription requires a Groq API key. "
                "Add GROQ_API_KEY to your .env file. "
                "Get your free API key at https://console.groq.com/keys"
            )
        try:
            from groq import Groq
            _client = Groq(api_key=api_key)
        except ImportError as e:
            raise GroqNotConfiguredError(
                "Groq package is not installed. Run: pip install groq"
            ) from e
    return _client


def transcribe_audio(
    audio_data: bytes,
    filename: str = "audio.webm",
    language: str = "en",
) -> str:
    """
    Transcribe audio using Groq's Whisper API.
    
    Args:
        audio_data: Raw audio bytes
        filename: Original filename (used for format detection)
        language: Language code (default: "en")
        
    Returns:
        Transcribed text
        
    Raises:
        GroqNotConfiguredError: If GROQ_API_KEY is not set
    """
    client = get_groq_client()
    
    # Groq's API expects a file tuple: (filename, file_bytes)
    transcription = client.audio.transcriptions.create(
        file=(filename, audio_data),
        model="whisper-large-v3-turbo",
        temperature=0,
        language=language,
        response_format="verbose_json",
    )
    
    logger.info(f"Transcribed audio: {len(audio_data)} bytes -> {len(transcription.text)} chars")
    return transcription.text
