import json

from file_utils import is_jwt, is_valid_token
from logtools import maybe_log_message
from token_storage import TokenStorage


class TokenManager(object):
    def __init__(self, server_name, post_data_fn, logger):
        self.server_name = server_name
        self.post_data = post_data_fn
        self.logger = logger
        self.storage = TokenStorage(server_name)
        self.auth_token = None

    def get_valid_token(self):
        token = self.storage.load_token()
        if token and is_jwt(token):
            self.auth_token = token
            return token

        token = self._fetch_new_token()
        if token:
            self.storage.save_token(token)
            self.auth_token = token
            return token

        raise Exception('Failed to obtain a valid token')

    def _fetch_new_token(self):
        url = 'agent/register/'
        payload = {'name': self.server_name}

        try:
            raw_response = self.post_data(
                url=url,
                payload=payload,
                to_controller=True,
                fail_silently=False,
                Content_Type='application/json'
            )

            if not raw_response:
                maybe_log_message(
                    'Empty response from controller',
                    logger=self.logger,
                    extra={
                        'agent_name': self.server_name,
                        'step': 'auth',
                        'status': 'empty_response'
                    }
                )
                return None

            try:
                data = json.loads(raw_response)
            except ValueError:
                maybe_log_message(
                    'Invalid JSON response',
                    logger=self.logger,
                    extra={
                        'agent_name': self.server_name,
                        'step': 'auth',
                        'status': 'json_error'
                    }
                )
                return None

            token = data.get('token')
            if is_jwt(token):
                return token

            maybe_log_message(
                'Received invalid token format',
                logger=self.logger,
                extra={
                    'agent_name': self.server_name,
                    'step': 'auth',
                    'status': 'not_jwt'
                }
            )
            return None

        except Exception:
            maybe_log_message(
                'Unexpected error during token fetch',
                logger=self.logger,
                extra={
                    'agent_name': self.server_name,
                    'step': 'auth',
                    'status': 'exception'
                }
            )
            return None
