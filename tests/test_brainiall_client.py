from __future__ import annotations

import io
import json
import struct
import traceback

import httpx
import pytest
from dify_plugin.errors.model import (
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeRateLimitError,
    InvokeServerUnavailableError,
)

from brainiall_api import (
    DEFAULT_VOICE,
    MAX_AUDIO_BYTES,
    MAX_TTS_CHARACTERS,
    BrainiallApiClient,
    BrainiallAuthorizationError,
    BrainiallBadRequestError,
    BrainiallProtocolError,
    BrainiallRateLimitError,
    BrainiallServerError,
    BrainiallTransportError,
    format_transcript,
    validate_wav,
)
from models.speech2text.speech2text import BrainiallSpeech2TextModel
from models.tts.tts import BrainiallText2SpeechModel

SECRET = "brn_test_should_never_appear"


def make_pcm_wav(audio_data: bytes = b"\x00\x00") -> bytes:
    format_data = struct.pack("<HHIIHH", 1, 1, 24_000, 48_000, 2, 16)
    format_chunk = b"fmt " + len(format_data).to_bytes(4, "little") + format_data
    data_chunk = b"data" + len(audio_data).to_bytes(4, "little") + audio_data
    if len(audio_data) % 2:
        data_chunk += b"\x00"
    riff_body = b"WAVE" + format_chunk + data_chunk
    return b"RIFF" + len(riff_body).to_bytes(4, "little") + riff_body


VALID_WAV = make_pcm_wav()


def rendered_exception(error: BaseException) -> str:
    return "".join(traceback.format_exception(error))


def client_for(handler) -> BrainiallApiClient:
    return BrainiallApiClient(SECRET, transport=httpx.MockTransport(handler))


def test_credentials_validation_uses_bearer_header_and_redacts_provider_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.brainiall.com/v1/tts/voices")
        assert request.headers["authorization"] == f"Bearer {SECRET}"
        return httpx.Response(401, text=f"credential {SECRET} rejected")

    with pytest.raises(BrainiallAuthorizationError) as caught:
        client_for(handler).validate_credentials()

    assert SECRET not in str(caught.value)
    assert "credential" in str(caught.value).lower()
    assert SECRET not in repr(caught.value)
    assert SECRET not in rendered_exception(caught.value)


@pytest.mark.parametrize(
    "payload",
    [
        {"voices": [{"id": "pf_dora", "name": "Dora"}], "defaultVoice": "pf_dora"},
        [{"voice_id": "pf_dora", "name": "Dora"}],
        ["pf_dora"],
    ],
)
def test_credentials_validation_preserves_plausible_real_voice_shapes(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client_for(handler).validate_credentials()


@pytest.mark.parametrize(
    "payload",
    [{}, {"voices": []}, {"voices": [{}]}, {"voices": [{"name": "Dora"}]}, [], "ok", None],
)
def test_credentials_validation_rejects_generic_json(payload: object) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with pytest.raises(BrainiallProtocolError):
        client_for(handler).validate_credentials()


def test_credentials_validation_rejects_malformed_json_without_leaking_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=f"not-json {SECRET}")

    with pytest.raises(BrainiallProtocolError) as caught:
        client_for(handler).validate_credentials()

    assert SECRET not in str(caught.value)
    assert SECRET not in repr(caught.value)
    assert SECRET not in rendered_exception(caught.value)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (400, BrainiallBadRequestError),
        (401, BrainiallAuthorizationError),
        (403, BrainiallAuthorizationError),
        (422, BrainiallBadRequestError),
        (429, BrainiallRateLimitError),
        (500, BrainiallServerError),
        (503, BrainiallServerError),
    ],
)
def test_http_statuses_map_to_sanitized_errors(status: int, expected: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=f"sensitive body {SECRET}")

    with pytest.raises(expected) as caught:
        client_for(handler).validate_credentials()

    assert SECRET not in str(caught.value)
    assert "sensitive body" not in str(caught.value)
    assert SECRET not in repr(caught.value)
    assert SECRET not in rendered_exception(caught.value)


def test_transport_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout(f"timeout while using {SECRET}", request=request)

    with pytest.raises(BrainiallTransportError) as caught:
        client_for(handler).validate_credentials()

    assert SECRET not in str(caught.value)
    assert caught.value.__cause__ is None
    assert SECRET not in repr(caught.value)
    assert SECRET not in rendered_exception(caught.value)


def test_redirect_is_not_followed_or_leaked() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            302,
            headers={"location": f"https://redirect.invalid/voices?token={SECRET}"},
        )

    with pytest.raises(BrainiallProtocolError) as caught:
        client_for(handler).validate_credentials()

    assert len(requests) == 1
    assert requests[0].url.host == "api.brainiall.com"
    assert SECRET not in str(caught.value)
    assert SECRET not in rendered_exception(caught.value)


def test_transport_failure_is_attempted_only_once() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(BrainiallTransportError):
        client_for(handler).validate_credentials()

    assert attempts == 1


def test_default_http_transport_explicitly_disables_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured_retries: list[int] = []

    def transport_factory(*, retries: int) -> httpx.BaseTransport:
        configured_retries.append(retries)
        return httpx.MockTransport(
            lambda request: httpx.Response(200, json={"voices": [{"id": "pf_dora"}]})
        )

    monkeypatch.setattr(httpx, "HTTPTransport", transport_factory)
    BrainiallApiClient(SECRET).validate_credentials()

    assert configured_retries == [0]


def test_transcription_groups_consecutive_words_by_speaker() -> None:
    payload = {
        "text": "Bom dia. Tudo bem?",
        "words": [
            {"word": "Bom", "speaker": 0, "start": 0.0, "end": 0.2},
            {"word": "dia", "speaker": 0, "start": 0.2, "end": 0.4},
            {"word": ".", "speaker": 0, "start": 0.4, "end": 0.5},
            {"word": "Tudo", "speaker": 1, "start": 0.5, "end": 0.8},
            {"word": "bem", "speaker": 1, "start": 0.8, "end": 1.0},
            {"word": "?", "speaker": 1, "start": 1.0, "end": 1.1},
        ],
    }

    assert format_transcript(payload) == "Speaker 0: Bom dia.\nSpeaker 1: Tudo bem?"


def test_partial_speaker_metadata_falls_back_without_dropping_words() -> None:
    payload = {
        "text": "Uma frase completa.",
        "words": [
            {"word": "Uma", "speaker": 0},
            {"word": "frase"},
            {"word": "completa", "speaker": 0},
            {"word": ".", "speaker": 0},
        ],
    }

    assert format_transcript(payload) == "Uma frase completa."


def test_transcription_request_uses_fixed_pt_br_contract() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.brainiall.com/v1/whisper/transcribe")
        body = request.content
        assert b'name="language"' in body and b"pt" in body
        assert b'name="diarize"' in body and b"true" in body
        assert b'name="audio"' in body and b"audio-data" in body
        return httpx.Response(200, json={"text": "Ola"})

    audio = io.BytesIO(b"audio-data")
    audio.name = "sample.wav"
    assert client_for(handler).transcribe(audio) == "Ola"


def test_transcription_sends_only_the_basename() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert b'filename="private-call.wav"' in request.content
        assert b"Users\\Operator" not in request.content
        return httpx.Response(200, json={"text": "Ola"})

    audio = io.BytesIO(b"audio-data")
    audio.name = r"C:\Users\Operator\private-call.wav"
    assert client_for(handler).transcribe(audio) == "Ola"


def test_transcription_accepts_exactly_25_mb() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"text": "Limite aceito"})

    audio = io.BytesIO(b"a" * MAX_AUDIO_BYTES)
    audio.name = "limit.wav"
    assert client_for(handler).transcribe(audio) == "Limite aceito"
    assert calls == 1


def test_transcription_rejects_more_than_25_mb_before_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"text": "unexpected"})

    audio = io.BytesIO(b"a" * (MAX_AUDIO_BYTES + 1))
    with pytest.raises(BrainiallBadRequestError, match="25 MB"):
        client_for(handler).transcribe(audio)
    assert calls == 0


def test_tts_falls_back_to_default_voice_and_sends_fixed_speed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://api.brainiall.com/v1/tts/synthesize")
        payload = json.loads(request.content)
        assert payload == {"text": "Ola, mundo!", "voice": DEFAULT_VOICE, "speed": 1.0}
        return httpx.Response(200, content=VALID_WAV, headers={"content-type": "audio/wav"})

    assert client_for(handler).synthesize("  Ola, mundo!  ", "arbitrary-voice") == VALID_WAV


def test_tts_preserves_each_supported_voice() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content)["voice"])
        return httpx.Response(200, content=VALID_WAV)

    client = client_for(handler)
    for voice in ("pf_dora", "pm_alex", "pm_santa"):
        client.synthesize("Teste", voice)

    assert seen == ["pf_dora", "pm_alex", "pm_santa"]


def test_tts_accepts_exactly_4000_characters() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        assert len(json.loads(request.content)["text"]) == MAX_TTS_CHARACTERS
        return httpx.Response(200, content=VALID_WAV)

    assert client_for(handler).synthesize("a" * MAX_TTS_CHARACTERS, "pf_dora") == VALID_WAV
    assert calls == 1


def test_tts_rejects_more_than_4000_characters_before_network() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=VALID_WAV)

    with pytest.raises(BrainiallBadRequestError, match="4000 characters"):
        client_for(handler).synthesize("a" * (MAX_TTS_CHARACTERS + 1), "pf_dora")
    assert calls == 0


def test_wav_validation_rejects_non_audio_success_response() -> None:
    with pytest.raises(BrainiallProtocolError):
        validate_wav(b'{"error":"not audio"}')


def test_wav_validation_accepts_riff_wave_header() -> None:
    assert validate_wav(VALID_WAV) == VALID_WAV


@pytest.mark.parametrize(
    "payload",
    [
        b"RIFF" + (4).to_bytes(4, "little") + b"WAVE",
        b"RIFF" + (16).to_bytes(4, "little") + b"WAVEfmt " + (100).to_bytes(4, "little"),
        make_pcm_wav(b""),
    ],
)
def test_wav_validation_rejects_header_only_truncated_or_empty_audio(payload: bytes) -> None:
    with pytest.raises(BrainiallProtocolError):
        validate_wav(payload)


@pytest.mark.parametrize("model_class", [BrainiallSpeech2TextModel, BrainiallText2SpeechModel])
def test_dify_models_expose_complete_error_mapping(model_class: type) -> None:
    model = object.__new__(model_class)
    mapping = model._invoke_error_mapping

    assert BrainiallTransportError in mapping[InvokeConnectionError]
    assert BrainiallServerError in mapping[InvokeServerUnavailableError]
    assert BrainiallProtocolError in mapping[InvokeServerUnavailableError]
    assert BrainiallRateLimitError in mapping[InvokeRateLimitError]
    assert BrainiallAuthorizationError in mapping[InvokeAuthorizationError]
    assert BrainiallBadRequestError in mapping[InvokeBadRequestError]


def test_dify_tts_model_lists_only_configured_pt_br_voices() -> None:
    model = object.__new__(BrainiallText2SpeechModel)

    assert model.get_tts_model_voices("brainiall-tts-pt-br", {}) == [
        {"name": "Dora (Brazilian Portuguese)", "value": "pf_dora"},
        {"name": "Alex (Brazilian Portuguese)", "value": "pm_alex"},
        {"name": "Santa (Brazilian Portuguese)", "value": "pm_santa"},
    ]
