import logging

from ..exceptions import AuthenticationError
from .logtools import maybe_log_message
from .token_manager import TokenManager


class AgentCommunicator(object):
    """
    Handles authenticated communication between an agent and a remote server.

    This class manages token retrieval using a TokenManager and uses
    the provided `post_data_fn` to send authenticated requests.
    """

    def __init__(self, server_name, post_data_fn, logger):
        """
        Initialize the AgentCommunicator.

        Args:
            server_name (str): Identifier for the server/agent instance.
            post_data_fn (callable): Function used to send data.
                Expected signature:
                `post_data_fn(url, payload, api_key=..., **kwargs)`
            logger (logging.Logger): Logger instance for structured logging.
        """
        self.server_name = server_name
        self.post_data_fn = post_data_fn
        self.logger = logger
        try:
            self.token_manager = TokenManager(
                server_name,
                post_data_fn,
                logger
            )
        except Exception as e:
            maybe_log_message(
                'Failed to initialize TokenManager: %s' % e,
                logger=self.logger,
                level=logging.ERROR,
            )
            self.token_manager = None

    def post_data_with_auth(self, url, payload, **kwargs):
        """
        Send data to a remote server with authentication.

        This method retrieves a valid token using TokenManager,
        logs an error if it fails, and raises an exception.
        If a token is available, it forwards the request using `post_data_fn`.

        Args:
            url (str): The target URL to send data to.
            payload (dict): JSON-serializable data to send.
            **kwargs: Additional arguments passed to `post_data`, such as:
            - timeout (int): Request timeout in seconds.
            - max_retries (int): Number of retry attempts on failure.
            - headers (dict): Additional headers to include.

        Returns:
            Response object returned by `post_data_fn`.

        Raises:
            Exception: If no valid token could be retrieved or request fails.
        """
        if not self.token_manager:
            maybe_log_message(
                'TokenManager is not initialized',
                logger=self.logger,
                level=logging.ERROR,
            )
            raise Exception('TokenManager is not initialized')

        try:
            token = self.token_manager.get_valid_token()
        except Exception as e:
            maybe_log_message(
                'Error retrieving token: %s' % e,
                logger=self.logger,
                level=logging.ERROR,
            )
            raise Exception('Token retrieval failed: %s' % e)

        if not token:
            maybe_log_message(
                'Token retrieval failed',
                logger=self.logger,
                level=logging.ERROR,
            )
            raise AuthenticationError(
                message='No valid token available for authentication.',
                server_name=self.server_name
            )

        try:
            return self.post_data_fn(
                url=url,
                payload=payload,
                to_controller=True,
                api_key=token,
                **kwargs
            )
        except Exception as e:
            maybe_log_message(
                'Error sending authenticated request: %s' % e,
                logger=self.logger,
                level=logging.ERROR,
            )
            raise
