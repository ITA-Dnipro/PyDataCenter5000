import json
import logging

from ..exceptions import TokenFetchError
from .file_utils import is_jwt
from .logtools import maybe_log_message
from .token_storage import TokenStorage


class TokenManager(object):
    """
    Manages authentication tokens for an agent.

    Handles:
    - Loading cached tokens
    - Fetching new tokens from the controller
    - Validating token format
    - Logging token-related issues
    """

    REGISTER_ENDPOINT = 'agent/register/'

    def __init__(self, server_name, post_data_fn, logger):
        """
        Args:
            server_name (str): Identifier for the current agent.
            post_data_fn (callable): Function used to send POST requests.
            logger (logging.Logger): Logger for recording events.
        """
        self.server_name = server_name
        self.post_data = post_data_fn
        self.logger = logger
        self.storage = TokenStorage(server_name)
        self.auth_token = None

    def get_valid_token(self):
        """
        Retrieve a valid JWT token.

        First attempts to load a stored token. If unavailable or invalid,
        attempts to fetch a new token from the controller.

        Returns:
            str: A valid JWT token.

        Raises:
            TokenFetchError: If no valid token could be obtained.
        """
        token = self.storage.load_token()
        if token and is_jwt(token):
            self.auth_token = token
            return token

        token = self._fetch_new_token()
        if token:
            self.storage.save_token(token)
            self.auth_token = token
            return token

        raise TokenFetchError(
            'Failed to obtain a valid token for server: %s' % self.server_name
        )

    def _fetch_new_token(self):
        """
        Request a new token from the controller.

        Returns:
            str or None: New JWT token if successful, else None.
        """
        payload = {'name': self.server_name}

        try:
            raw_response = self.post_data(
                url=self.REGISTER_ENDPOINT,
                payload=payload,
                to_controller=True,
                fail_silently=False,
                Content_Type='application/json'
            )

            if not raw_response:
                maybe_log_message(
                    'Empty response from controller',
                    logger=self.logger,
                    level=logging.WARNING
                )
                return None

            try:
                data = json.loads(raw_response)
            except ValueError:
                maybe_log_message(
                    'Invalid JSON response',
                    logger=self.logger,
                    level=logging.ERROR
                )
                return None

            token = data.get('token')
            if is_jwt(token):
                return token

            maybe_log_message(
                'Received invalid token format',
                logger=self.logger,
                level=logging.WARNING
            )
            return None

        except Exception as e:
            maybe_log_message(
                'Unexpected error during token fetch: %s' % e,
                logger=self.logger,
                level=logging.ERROR
            )
            return None
