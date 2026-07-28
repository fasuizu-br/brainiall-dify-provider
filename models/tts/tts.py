from collections.abc import Generator

from dify_plugin import TTSModel
from dify_plugin.errors.model import (
    CredentialsValidateFailedError,
    InvokeAuthorizationError,
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
    InvokeRateLimitError,
    InvokeServerUnavailableError,
)

from brainiall_api import (
    VOICE_IDS,
    BrainiallApiClient,
    BrainiallAPIError,
    BrainiallAuthorizationError,
    BrainiallBadRequestError,
    BrainiallProtocolError,
    BrainiallRateLimitError,
    BrainiallServerError,
    BrainiallTransportError,
)

VOICE_NAMES = {
    "pf_dora": "Dora (Brazilian Portuguese)",
    "pm_alex": "Alex (Brazilian Portuguese)",
    "pm_santa": "Santa (Brazilian Portuguese)",
}


class BrainiallText2SpeechModel(TTSModel):
    def _invoke(
        self,
        model: str,
        tenant_id: str,
        credentials: dict,
        content_text: str,
        voice: str,
        user: str | None = None,
    ) -> bytes | Generator[bytes, None, None]:
        return BrainiallApiClient(credentials.get("api_key")).synthesize(content_text, voice)

    def get_tts_model_voices(
        self,
        model: str,
        credentials: dict,
        language: str | None = None,
    ) -> list[dict[str, str]]:
        return [{"name": VOICE_NAMES[voice], "value": voice} for voice in VOICE_IDS]

    def validate_credentials(
        self,
        model: str,
        credentials: dict,
        user: str | None = None,
    ) -> None:
        try:
            BrainiallApiClient(credentials.get("api_key")).validate_credentials()
        except BrainiallAuthorizationError:
            raise CredentialsValidateFailedError("Invalid BRAINIALL API key.") from None
        except BrainiallAPIError:
            raise CredentialsValidateFailedError(
                "BRAINIALL credentials could not be validated right now."
            ) from None

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {
            InvokeConnectionError: [BrainiallTransportError],
            InvokeServerUnavailableError: [BrainiallServerError, BrainiallProtocolError],
            InvokeRateLimitError: [BrainiallRateLimitError],
            InvokeAuthorizationError: [BrainiallAuthorizationError],
            InvokeBadRequestError: [BrainiallBadRequestError, ValueError],
        }
