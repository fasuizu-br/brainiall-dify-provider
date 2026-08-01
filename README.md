# BRAINIALL Speech provider for Dify

BRAINIALL Speech adds two predefined model capabilities to Dify:

- Brazilian Portuguese speech-to-text with speaker diarization.
- Brazilian Portuguese text-to-speech with three pt-BR voices.

The plugin calls only the fixed origin `https://api.brainiall.com`. It does not accept a
custom API base URL, follow redirects, retry requests, or log API keys and user content.

## Setup

1. Sign in at [BRAINIALL](https://app.brainiall.com) and create a dedicated API key.
2. Install the released `.difypkg` in Dify Plugin Center.
3. Open **Model Providers → BRAINIALL Speech** and enter the dedicated API key.
4. Select `brainiall-whisper-pt-br` for transcription or `brainiall-tts-pt-br` for
   synthesis in a Dify application or workflow.

Credential validation uses the read-only `GET /v1/tts/voices` endpoint. Validation does
not synthesize speech or transcribe a file.

The plugin itself is free and open source. BRAINIALL API usage is metered and may be
charged after the account's included credits; review the current pricing before production
use.

## Speech-to-text behavior

The plugin sends the uploaded audio to `POST /v1/whisper/transcribe` as multipart form
data with `language=pt` and `diarize=true`. The maximum accepted upload is 25 MB.

When the API returns word-level speaker values, consecutive words are grouped into lines
such as `Speaker 0: ...`. If speaker values are absent, the plugin returns the API's plain
`text` field.

## Text-to-speech behavior

The plugin sends text to `POST /v1/tts/synthesize` with speed `1.0`. It validates that a
successful response is a RIFF/WAVE document before returning it to Dify.

| Voice ID | Display name |
| --- | --- |
| `pf_dora` | Dora |
| `pm_alex` | Alex |
| `pm_santa` | Santa |

An empty or unsupported voice value falls back to `pf_dora`; arbitrary voice values are
never forwarded. Input is limited to 4,000 characters per invocation.

## Security and network boundary

- Authentication uses `Authorization: Bearer <API key>` over HTTPS.
- Requests have explicit connect, read, write, and pool timeouts.
- Automatic retries are disabled, preventing accidental duplicate billable operations.
- Redirect following is disabled, preventing credentials from being forwarded elsewhere.
- Error messages expose neither provider response bodies nor credentials.
- The plugin performs no command execution, filesystem writes, browser automation, SQL,
  or arbitrary URL fetching.

Because uploaded audio and synthesis text are sent to BRAINIALL, the Marketplace risk
classification is **medium**. See [PRIVACY.md](PRIVACY.md) for the exact data flow.

## Development

```bash
uv sync
uv run --with pytest --with ruff pytest -q
uv run --with pytest --with ruff ruff check .
python scripts/package_runtime.py
```

Tests use `httpx.MockTransport`; they do not contact BRAINIALL.
The packaging script copies an explicit runtime allowlist into a temporary directory, so
tests, caches, local environments, and development scripts cannot enter the `.difypkg`.

Source repository:
[github.com/fasuizu-br/brainiall-dify-provider](https://github.com/fasuizu-br/brainiall-dify-provider)

## Community integration examples

The [`examples/`](examples/) directory includes an n8n HTTP template for caller-owned
binary audio. It is a community example only: it is not an n8n partnership, it embeds no
credential, and it does not claim that the template is production-ready for every n8n
version.

## YouTube subtitle workflow templates

The [`examples/transcription/youtube-subtitles-srt-request.json`](examples/transcription/youtube-subtitles-srt-request.json)
recipe is a provider-neutral HTTP step for Dify or n8n: it keeps the API key in a
runtime secret, sends caller-owned audio to the fixed BRAINIALL origin, and exposes
the transcript and word timestamps needed to render SRT. It does not upload or publish
to YouTube. Pair it with the
[`youtube-subtitles-srt-quality-gate.json`](examples/transcription/youtube-subtitles-srt-quality-gate.json)
checks before a human performs the final platform upload. A no-code browser path is
available at [Preparar SRT para YouTube Studio](https://www.brainiall.com/transcreve/tools/youtube-subtitles-srt).

For Vimeo and Wistia teams, [`vimeo-wistia-caption-routing.json`](examples/transcription/vimeo-wistia-caption-routing.json)
keeps the media caller-owned and maps the reviewed SRT/WebVTT file to the correct
platform-specific human upload step. Pair it with
[`vimeo-wistia-caption-quality-gate.json`](examples/transcription/vimeo-wistia-caption-quality-gate.json).
These examples do not log in, publish, or claim an affiliation with Vimeo or Wistia.

For course creators, [`course-platform-caption-routing.json`](examples/transcription/course-platform-caption-routing.json)
maps the documented SRT/VTT handoff for Thinkific, Teachable, Podia, and Kajabi. Pair it
with [`course-platform-caption-quality-gate.json`](examples/transcription/course-platform-caption-quality-gate.json).
The examples remain caller-owned and do not log in, publish, or claim an affiliation with
any course platform.

Support: [support@brainiall.com](mailto:support@brainiall.com)

## Current limitations

- Speech recognition is intentionally fixed to Portuguese (`pt`) with diarization on.
- TTS speed is intentionally fixed to `1.0`; the Dify TTS interface does not expose it.
- TTS returns one complete WAV response rather than streamed audio chunks.
- The package has passed mocked transport and SDK packaging tests. A valid-key live Dify
  smoke test is still pending; use the release candidate for evaluation, not an unreviewed
  production rollout.
- Server-side processing and retention are controlled by the BRAINIALL service, not by
  this plugin; review the current service privacy policy before production use.
