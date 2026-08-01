# Integration examples

These examples are community templates, not an n8n, Make, Sonix or platform partnership.
They call the fixed BRAINIALL API origin with a key owned by the person importing the
workflow. No key, audio, transcript or customer data is included in this repository.

## n8n: binary audio to diarized PT-BR JSON

`n8n-transcribe-binary-to-json.json` expects the incoming item to contain caller-owned
binary data under the `data` field. Before executing it:

1. Set `BRAINIALL_API_KEY` in the n8n process environment. Do not paste a live key into
   the imported workflow or commit it to a repository.
2. Produce a binary item using your own trigger or replace the Manual Trigger with a
   Google Drive, webhook or other source that you control.
3. Review consent, retention and the file's authorization before sending it to an
   external transcription service.
4. Import the JSON, run a small non-sensitive fixture and inspect the returned JSON.

The request is `POST https://api.brainiall.com/v1/whisper/transcribe` with multipart
field `audio`, `language=pt` and `diarize=true`. The template has a 120-second client
timeout and does not add retries. The service limits and current pricing remain the
source of truth; check them before production use.

This is a starting point, not a guarantee that every n8n version uses the same node
schema. Validate the imported workflow in your own n8n instance and keep the API key in
its secret store or environment. For support, use [support@brainiall.com](mailto:support@brainiall.com).
