from logtools import maybe_log_message
from token_manager import TokenManager


class AgentCommunicator(object):
    def __init__(self, server_name, post_data_fn, logger):
        self.server_name = server_name
        self.post_data = post_data_fn
        self.logger = logger
        self.token_manager = TokenManager(server_name, post_data_fn, logger)

    def post_data_with_auth(self, url, payload, **kwargs):
        token = self.token_manager.get_valid_token()
        if not token:
            maybe_log_message(
                'Token retrieval failed',
                logger=self.logger,
                extra={
                    'agent_name': self.server_name,
                    'step': 'auth',
                    'status': 'missing_token'
                }
            )
            raise Exception('No valid token available for authentication')

        return self.post_data(
            url=url,
            payload=payload,
            to_controller=True,
            api_key=token,
            **kwargs
        )
