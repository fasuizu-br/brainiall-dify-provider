# n8n + Transcreve BR (PT-BR)

This caller-owned workflow receives an authorized binary audio upload, sends it to the fixed BRAINIALL speech-to-text endpoint, and returns the JSON result to the webhook caller.

## Setup

1. Import `transcreve-ptbr-webhook.json` into your own n8n instance.
2. Configure the environment secret `BRAINIALL_API_KEY` in the n8n runtime. Do not put a key in the workflow JSON, webhook payload, or a public issue.
3. Activate the workflow and copy the production webhook URL.
4. POST a caller-owned audio file as multipart field `data`.

The workflow sends `language=pt` and `diarize=true`. Review transcript, speakers, timestamps, and retention before any downstream action. The workflow does not log in to, upload to, or publish on a third-party platform.

This is a community recipe, not an n8n partnership or a production guarantee for every n8n version. Processing is metered; confirm the current BRAINIALL pricing and account credits before a paid run.

See the bounded buyer-intent route: https://www.brainiall.com/transcreve/integracoes/n8n-transcreve-ptbr-webhook
