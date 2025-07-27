import os

import agents_infra.agents


class TokenStorage(object):
    def __init__(self, server_name):
        self.server_name = server_name

    def get_token_file_path(self, custom_path=None):
        if (
            custom_path and
            os.path.exists(custom_path) and
            os.access(custom_path, os.W_OK)
        ):
            return custom_path

        agents_path = os.path.dirname(agents_infra.agents.__file__)
        if os.path.exists(agents_path) and os.access(agents_path, os.W_OK):
            tokens_dir = os.path.join(agents_path, 'tokens')
            if not os.path.exists(tokens_dir):
                os.makedirs(tokens_dir)
            return os.path.join(tokens_dir, '%s.token' % self.server_name)

        return '/var/lib/agent/%s.token' % self.server_name

    def load_token(self, path=None):
        full_path = self.get_token_file_path(path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                return f.read().strip()
        return None

    def save_token(self, token, path=None):
        full_path = self.get_token_file_path(path)
        dir_path = os.path.dirname(full_path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(full_path, 'w') as f:
            f.write(token)
