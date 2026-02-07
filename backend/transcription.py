"""Audio transcription using Groq's Whisper API."""

import os
import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

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


def _is_retriable_error(exception: Exception) -> bool:
    """
    Determine if an exception should trigger a retry.

    Retries on transient failures:
    - Network/connection errors
    - Timeouts
    - Rate limits (429)
    - Server errors (5xx)

    Does NOT retry on permanent failures:
    - Authentication errors (401)
    - Bad request (400)
    - Payment required (402)
    - Permission denied (403)
    """
    try:
        from groq import (
            APIConnectionError,
            APITimeoutError,
            RateLimitError,
            InternalServerError,
        )

        # Retry on transient errors
        return isinstance(
            exception,
            (
                APIConnectionError,
                APITimeoutError,
                RateLimitError,
                InternalServerError,
            ),
        )
    except ImportError:
        # If groq is not installed, don't retry
        return False


@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(4),  # 1 initial attempt + 3 retries
    wait=wait_exponential(multiplier=1, min=1, max=10),  # 1s, 2s, 4s, 8s (capped at 10s)
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def transcribe_audio(
    audio_data: bytes,
    filename: str = "audio.webm",
    language: str = "en",
) -> str:
    """
    Transcribe audio using Groq's Whisper API with automatic retries.

    Retries on transient failures (network errors, timeouts, rate limits, server errors)
    with exponential backoff. Does not retry on permanent failures (auth, bad request).

    Args:
        audio_data: Raw audio bytes
        filename: Original filename (used for format detection)
        language: Language code (default: "en")

    Returns:
        Transcribed text

    Raises:
        GroqNotConfiguredError: If GROQ_API_KEY is not set
        Various Groq exceptions: If transcription fails after retries
    """
    client = get_groq_client()

    try:
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
    except Exception as e:
        # Check if this is a retriable error before allowing retry
        if not _is_retriable_error(e):
            logger.warning(f"Non-retriable error during transcription: {type(e).__name__}: {e}")
            raise
        # Retriable error - let tenacity handle the retry
        logger.warning(f"Retriable error during transcription: {type(e).__name__}: {e}")
        raise
