import json
import os

import pkg_resources


class AgentCommunication:
    def __init__(self, server_name, post_data_fn):
        """
        Initialize with a unique server name and a callable for posting data.

        Args:
            server_name (str): The agent's unique identifier.
            post_data_fn (callable): A method that sends HTTP POST data.
        """
        self.server_name = server_name
        self.auth_token = None
        self.post_data = post_data_fn

    def get_token_file_path(self, token_path=None):
        """
        Resolve the token storage file path.

        Args:
            token_path (str): Optional override for token path.

        Returns:
            str: Full path to the token file.
        """
        if token_path is None:
            token_path = pkg_resources.resource_filename(
                self.__class__.__module__,
                f'tokens/{self.server_name}.token'
            )
        return token_path

    def save_local_token(self, token, token_path=None):
        """
        Save the token to a local file.

        Args:
            token (str): The authentication token.
            token_path (str): Optional override for token path.
        """
        path = self.get_token_file_path(token_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'w') as f:
            f.write(token)

    def load_local_token(self, token_path=None):
        """
        Load the token from the local file, if present.

        Args:
            token_path (str): Optional override for token path.

        Returns:
            str or None: The token if present, else None.
        """
        path = self.get_token_file_path(token_path)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read().strip()
        return None

    def register_agent_if_needed(self):
        """
        Ensure the agent is registered with the controller.
        Attempts to reuse a local token before requesting a new one.

        Raises:
            Exception: If registration fails or no token is returned.
        """
        token = self.load_local_token()
        if token:
            self.auth_token = token
            return

        payload = {'name': self.server_name}
        url = 'agent/register/'

        try:
            response = self.post_data(
                url=url,
                payload=payload,
                to_controller=True,
                fail_silently=False,
                Content_Type='application/json'
            )
            if not response:
                raise Exception('Empty response from server.')

            data = json.loads(response)
            token = data.get('token')

            if token:
                self.save_local_token(token)
                self.auth_token = token
            else:
                raise Exception('No token received from server.')
        except Exception as e:
            raise Exception(f'Could not register agent: {str(e)}')

    def post_data_with_auth(self, url, payload, **kwargs):
        """
        Send authenticated data to the controller.

        Automatically ensures registration and adds Authorization token.

        Args:
            url (str): The API endpoint.
            payload (dict): The data payload.
            **kwargs: Any extra parameters for post_data.

        Returns:
            Response: The controller response.

        Raises:
            Exception: If token cannot be retrieved or registration fails.
        """
        if not self.auth_token:
            self.register_agent_if_needed()

        if not self.auth_token:
            raise Exception('Authorization token missing after registration.')

        return self.post_data(
            url=url,
            payload=payload,
            to_controller=True,
            api_key=self.auth_token,
            **kwargs
        )
