import base64
import os

from agents_infra.utils import configtools

cfg = configtools.load_global_config()
if cfg:
    auth_token_type = configtools.get_config_option(
        cfg, 'controller', 'auth_token_type', default='Basic'
    )
else:
    auth_token_type = 'Basic'


class AuthManager(object):
    def __init__(self, auth_type):
        self.auth_type = auth_type

    def get_key(self):
        if self.auth_type == 'Basic':
            login = os.environ.get('DJANGO_LOGIN')
            password = os.environ.get('DJANGO_PASSWORD')
            if login is None or password is None:
                return None
            creds = ('%s:%s' % (login, password)).encode('utf-8')
            return base64.b64encode(creds)
        # Add other strategies here (e.g., Bearer)
        return None


Authentication = AuthManager(auth_token_type)
