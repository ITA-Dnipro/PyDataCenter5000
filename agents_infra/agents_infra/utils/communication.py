import json

import pkg_resources
from file_utils import read_from_file, write_to_file
from logtools import maybe_log_message


class AgentCommunication:
    def __init__(self, server_name, post_data_fn, logger):
        self.server_name = server_name
        self.auth_token = None
        self.post_data = post_data_fn
        self.logger = logger

    def get_token_file_path(self, token_path=None):
        if token_path is None:
            token_path = pkg_resources.resource_filename(
                self.__class__.__module__,
                f'tokens/{self.server_name}.token'
            )
        return token_path

    def save_local_token(self, token, token_path=None):
        path = self.get_token_file_path(token_path)
        write_to_file(path, token)

    def load_local_token(self, token_path=None):
        path = self.get_token_file_path(token_path)
        return read_from_file(path)

    def register_agent_if_needed(self):
        token = self.load_local_token()
        if token:
            self.auth_token = token
            return

        token = self._request_token_from_controller()
        if token:
            self.save_local_token(token)
            self.auth_token = token
        else:
            maybe_log_message(
                'Agent registration failed',
                logger=self.logger
            )
            raise Exception('Agent registration failed: no token received')

    def post_data_with_auth(self, url, payload, **kwargs):
        if not self.auth_token:
            self.register_agent_if_needed()

        if not self.auth_token:
            maybe_log_message(
                'No auth token provided',
                logger=self.logger
            )
            raise Exception('Authorization token missing after registration.')

        return self.post_data(
            url=url,
            payload=payload,
            to_controller=True,
            api_key=self.auth_token,
            **kwargs
        )

    def _request_token_from_controller(self):
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
                    'The response is empty',
                    logger=self.logger
                )
                raise Exception('Empty response from controller')

            try:
                data = json.loads(raw_response)
            except json.JSONDecodeError as e:
                maybe_log_message(
                    'Invalid response',
                    logger=self.logger
                )
                raise Exception('Invalid JSON response: %s' % e)

            return data.get('token')
        except Exception as e:
            maybe_log_message(
                'Unexpected error',
                logger=self.logger
            )
            raise Exception('Unexpected error %s' % e)
