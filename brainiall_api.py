from __future__ import annotations

import mimetypes
import re
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any

import httpx

API_BASE = "https://api.brainiall.com"
STT_PATH = "/v1/whisper/transcribe"
TTS_PATH = "/v1/tts/synthesize"
VOICES_PATH = "/v1/tts/voices"

DEFAULT_VOICE = "pf_dora"
VOICE_IDS = ("pf_dora", "pm_alex", "pm_santa")
MAX_AUDIO_BYTES = 25 * 1024 * 1024
MAX_TTS_CHARACTERS = 4_000

VALIDATION_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
STT_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=60.0, pool=5.0)
TTS_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=30.0, pool=5.0)


class BrainiallAPIError(Exception):
    """Base exception whose message is safe to display to a Dify administrator."""


class BrainiallAuthorizationError(BrainiallAPIError):
    pass


class BrainiallBadRequestError(BrainiallAPIError):
    pass


class BrainiallRateLimitError(BrainiallAPIError):
    pass


class BrainiallServerError(BrainiallAPIError):
    pass


class BrainiallTransportError(BrainiallAPIError):
    pass


class BrainiallProtocolError(BrainiallAPIError):
    pass


def normalize_voice(voice: str | None) -> str:
    """Return a supported voice, falling back without forwarding arbitrary values."""
    return voice if voice in VOICE_IDS else DEFAULT_VOICE


def validate_wav(payload: bytes) -> bytes:
    """Validate a complete RIFF/WAVE container with format and non-empty data chunks."""
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WAVE":
        raise BrainiallProtocolError("BRAINIALL returned an invalid audio response.")

    declared_riff_size = int.from_bytes(payload[4:8], "little")
    if declared_riff_size < 4:
        raise BrainiallProtocolError("BRAINIALL returned an invalid audio response.")
    if declared_riff_size != 0xFFFFFFFF and declared_riff_size + 8 > len(payload):
        raise BrainiallProtocolError("BRAINIALL returned an incomplete audio response.")

    found_format = False
    found_audio_data = False
    offset = 12
    while offset + 8 <= len(payload):
        chunk_id = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        chunk_start = offset + 8
        chunk_end = chunk_start + chunk_size
        if chunk_end > len(payload):
            raise BrainiallProtocolError("BRAINIALL returned an incomplete audio response.")

        if chunk_id == b"fmt ":
            if chunk_size < 16:
                raise BrainiallProtocolError("BRAINIALL returned an invalid audio response.")
            channels = int.from_bytes(payload[chunk_start + 2 : chunk_start + 4], "little")
            sample_rate = int.from_bytes(payload[chunk_start + 4 : chunk_start + 8], "little")
            block_align = int.from_bytes(payload[chunk_start + 12 : chunk_start + 14], "little")
            if channels < 1 or sample_rate < 1 or block_align < 1:
                raise BrainiallProtocolError("BRAINIALL returned an invalid audio response.")
            found_format = True
        elif chunk_id == b"data" and chunk_size > 0:
            found_audio_data = True

        offset = chunk_end + (chunk_size % 2)

    if not found_format or not found_audio_data:
        raise BrainiallProtocolError("BRAINIALL returned an invalid audio response.")
    return payload


def _is_plausible_voice_entry(entry: object) -> bool:
    if isinstance(entry, str):
        return bool(entry.strip())
    if not isinstance(entry, Mapping):
        return False
    return any(
        isinstance(entry.get(field), str) and bool(entry[field].strip())
        for field in ("id", "voice_id", "value", "mode")
    )


def validate_voices_payload(payload: object) -> None:
    """Accept documented and legacy voice-list envelopes while rejecting generic JSON."""
    voices = payload.get("voices") if isinstance(payload, Mapping) else payload
    if not isinstance(voices, list) or not voices or not any(
        _is_plausible_voice_entry(entry) for entry in voices
    ):
        raise BrainiallProtocolError(
            "BRAINIALL returned an invalid credential-validation response."
        )


def _join_tokens(tokens: list[str]) -> str:
    result = ""
    for token in tokens:
        clean = token.strip()
        if not clean:
            continue
        if not result:
            result = clean
        elif re.match(r"^[,.;:!?%\)\]\}]", clean) or result.endswith(("(", "[", "{")):
            result += clean
        else:
            result += f" {clean}"
    return result


def format_transcript(payload: Mapping[str, Any]) -> str:
    """Render consecutive diarized words as speaker-labelled lines when available."""
    raw_text = payload.get("text")
    fallback_text = raw_text.strip() if isinstance(raw_text, str) else ""
    words = payload.get("words")
    if not isinstance(words, list):
        if fallback_text:
            return fallback_text
        raise BrainiallProtocolError("BRAINIALL returned an invalid transcription response.")

    labelled_words: list[tuple[str, str]] = []
    all_tokens: list[str] = []
    has_unlabelled_token = False
    for item in words:
        if not isinstance(item, Mapping):
            continue
        token = item.get("word") if isinstance(item.get("word"), str) else item.get("text")
        if not isinstance(token, str) or not token.strip():
            continue
        all_tokens.append(token)
        speaker = item.get("speaker")
        if speaker is None:
            has_unlabelled_token = True
            continue
        speaker_label = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(speaker).strip()).strip("_")[:64]
        if speaker_label:
            labelled_words.append((speaker_label, token))
        else:
            has_unlabelled_token = True

    if not labelled_words or has_unlabelled_token:
        if fallback_text:
            return fallback_text
        if text := _join_tokens(all_tokens):
            return text
        raise BrainiallProtocolError("BRAINIALL returned an empty transcription response.")

    groups: list[tuple[str, list[str]]] = []
    for speaker, token in labelled_words:
        if not groups or groups[-1][0] != speaker:
            groups.append((speaker, [token]))
        else:
            groups[-1][1].append(token)
    return "\n".join(f"Speaker {speaker}: {_join_tokens(tokens)}" for speaker, tokens in groups)


class BrainiallApiClient:
    """Small fixed-origin API client with explicit timeouts and zero automatic retries."""

    def __init__(
        self,
        api_key: object,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        key = api_key.strip() if isinstance(api_key, str) else ""
        if not key:
            raise BrainiallAuthorizationError("A BRAINIALL API key is required.")
        self._api_key = key
        self._transport = transport

    def _client(self, timeout: httpx.Timeout) -> httpx.Client:
        transport = self._transport or httpx.HTTPTransport(retries=0)
        return httpx.Client(
            base_url=API_BASE,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json, audio/wav",
                "User-Agent": "brainiall-dify-provider/0.1.0",
            },
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status in (401, 403):
            raise BrainiallAuthorizationError("BRAINIALL rejected the API credentials.")
        if status == 429:
            raise BrainiallRateLimitError("BRAINIALL rate limit reached. Try again later.")
        if status in (408, 425) or status >= 500:
            raise BrainiallServerError("BRAINIALL service is temporarily unavailable.")
        if 400 <= status < 500:
            raise BrainiallBadRequestError("BRAINIALL rejected the request.")
        raise BrainiallProtocolError("BRAINIALL returned an unexpected HTTP response.")

    @staticmethod
    def _request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = client.request(method, path, **kwargs)
        except httpx.TransportError:
            raise BrainiallTransportError("Could not connect to BRAINIALL.") from None
        BrainiallApiClient._raise_for_status(response)
        return response

    def validate_credentials(self) -> None:
        with self._client(VALIDATION_TIMEOUT) as client:
            response = self._request(client, "GET", VOICES_PATH)
        try:
            payload = response.json()
        except ValueError:
            raise BrainiallProtocolError(
                "BRAINIALL returned an invalid credential-validation response."
            ) from None
        validate_voices_payload(payload)

    def transcribe(self, file: IO[bytes]) -> str:
        audio = file.read(MAX_AUDIO_BYTES + 1)
        if not audio:
            raise BrainiallBadRequestError("The audio file is empty.")
        if len(audio) > MAX_AUDIO_BYTES:
            raise BrainiallBadRequestError("The audio file exceeds the 25 MB limit.")

        raw_name = getattr(file, "name", "")
        if isinstance(raw_name, str) and raw_name:
            filename = Path(raw_name.replace("\\", "/")).name[:255] or "audio.wav"
        else:
            filename = "audio.wav"
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with self._client(STT_TIMEOUT) as client:
            response = self._request(
                client,
                "POST",
                STT_PATH,
                data={"language": "pt", "diarize": "true"},
                files={"audio": (filename, audio, content_type)},
            )
        try:
            payload = response.json()
        except ValueError:
            raise BrainiallProtocolError(
                "BRAINIALL returned an invalid transcription response."
            ) from None
        if not isinstance(payload, Mapping):
            raise BrainiallProtocolError("BRAINIALL returned an invalid transcription response.")
        return format_transcript(payload)

    def synthesize(self, content_text: str, voice: str | None) -> bytes:
        text = content_text.strip() if isinstance(content_text, str) else ""
        if not text:
            raise BrainiallBadRequestError("Text-to-speech input must not be empty.")
        if len(text) > MAX_TTS_CHARACTERS:
            raise BrainiallBadRequestError(
                f"Text-to-speech input exceeds {MAX_TTS_CHARACTERS} characters."
            )

        with self._client(TTS_TIMEOUT) as client:
            response = self._request(
                client,
                "POST",
                TTS_PATH,
                json={"text": text, "voice": normalize_voice(voice), "speed": 1.0},
            )
        return validate_wav(response.content)
