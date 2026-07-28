from collections.abc import Mapping

from dify_plugin import ModelProvider
from dify_plugin.errors.model import CredentialsValidateFailedError

from brainiall_api import BrainiallApiClient, BrainiallAPIError, BrainiallAuthorizationError


class BrainiallProvider(ModelProvider):
    def validate_provider_credentials(self, credentials: Mapping) -> None:
        """Validate credentials with the free, read-only BRAINIALL voices endpoint."""
        try:
            BrainiallApiClient(credentials.get("api_key")).validate_credentials()
        except BrainiallAuthorizationError:
            raise CredentialsValidateFailedError("Invalid BRAINIALL API key.") from None
        except BrainiallAPIError:
            raise CredentialsValidateFailedError(
                "BRAINIALL credentials could not be validated right now."
            ) from None
