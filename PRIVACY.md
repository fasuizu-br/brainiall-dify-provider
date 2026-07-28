# Privacy notice

This notice describes the data flow of version 0.1.0 of the BRAINIALL Speech provider
plugin for Dify.

## Data sent to BRAINIALL

The plugin sends the following data over HTTPS only to `https://api.brainiall.com`:

- The configured BRAINIALL API key in an `Authorization: Bearer` header.
- Uploaded audio, the fixed language value `pt`, and the fixed diarization value `true`
  when speech-to-text is invoked.
- User-provided synthesis text, the selected supported voice ID, and fixed speed `1.0`
  when text-to-speech is invoked.
- The API key alone when the read-only voices endpoint is used for credential validation.

As with any HTTPS request, the BRAINIALL service infrastructure also receives transport and
security metadata such as source IP, timestamp, requested endpoint, status, latency, and byte
counts. This metadata is used for billing, rate limiting, fraud prevention, and security.

Uploaded audio and synthesis text may contain personal or confidential information.
Workspace administrators should obtain appropriate authorization before processing it.

## Collection, storage, and logging by the plugin

The plugin does not use Dify persistent storage, create local files, set cookies, collect
analytics, or send telemetry. It does not intentionally log API keys, uploaded audio,
synthesis text, transcripts, response bodies, or user identifiers. The API key remains in
Dify's provider credential store and is used only for authenticated BRAINIALL requests.

The plugin processes request and response data in memory for the duration of an invocation.
It has no control over server-side processing or retention performed by the BRAINIALL API.
Under the current [BRAINIALL Privacy Policy](https://app.brainiall.com/en/privacy), request
payloads are processed in memory and discarded after the response, anonymized usage aggregates
may be retained for up to 24 months, and error or authentication logs may be retained for up to
90 days. The public policy is the source of truth and may change independently of this package.
For access, correction, export, or deletion requests, contact
[privacy@brainiall.com](mailto:privacy@brainiall.com) or use the service's documented privacy
request channel.

## Third parties

The plugin code does not send data to any third party other than BRAINIALL. Dify itself and
the operator's infrastructure remain governed by their respective privacy and security
policies.

## Security boundary

The network destination is fixed in code. Redirects and automatic retries are disabled,
timeouts are explicit, successful TTS responses are validated as WAV data, and external
error bodies are not returned to users. The plugin does not execute user-controlled code,
commands, SQL, browser actions, filesystem operations, or arbitrary network requests.
