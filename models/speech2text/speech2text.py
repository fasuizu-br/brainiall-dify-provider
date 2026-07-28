from typing import IO

from dify_plugin import Speech2TextModel
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
    BrainiallApiClient,
    BrainiallAPIError,
    BrainiallAuthorizationError,
    BrainiallBadRequestError,
    BrainiallProtocolError,
    BrainiallRateLimitError,
    BrainiallServerError,
    BrainiallTransportError,
)


class BrainiallSpeech2TextModel(Speech2TextModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        file: IO[bytes],
        user: str | None = None,
    ) -> str:
        return BrainiallApiClient(credentials.get("api_key")).transcribe(file)

    def validate_credentials(self, model: str, credentials: dict) -> None:
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
