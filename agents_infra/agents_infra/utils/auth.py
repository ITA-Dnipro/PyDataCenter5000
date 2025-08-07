import base64
import os


class AuthStrategy(object):
    """Base class for authentication strategies."""

    def get_key(self):
        raise NotImplementedError


class BasicAuthStrategy(AuthStrategy):
    """Basic authentication using DJANGO_LOGIN and DJANGO_PASSWORD env vars"""

    def get_key(self):
        login = os.environ.get('DJANGO_LOGIN')
        password = os.environ.get('DJANGO_PASSWORD')
        if login is None or password is None:
            return None
        creds = ('%s:%s' % (login, password)).encode('utf-8')
        return base64.b64encode(creds)


class StaticTokenStrategy(AuthStrategy):
    """Static token authentication (placeholder)."""

    def get_key(self):
        # TODO: Implement static token retrieval (e.g., from env or config)
        return None


class JWTAuthStrategy(AuthStrategy):
    """JWT authentication (placeholder for future implementation)."""

    def get_key(self):
        # TODO: Implement JWT token retrieval (e.g., via HTTP request)
        return None


class AuthStrategyFactory(object):
    """
    Factory for creating authentication strategies based on a string argument.
    """

    @staticmethod
    def from_str(auth_type):
        auth_type = str(auth_type).lower()
        if auth_type == 'basic':
            return BasicAuthStrategy()
        elif auth_type == 'static':
            return StaticTokenStrategy()
        elif auth_type == 'jwt':
            return JWTAuthStrategy()
        else:
            raise ValueError('Unknown auth type: %s' % auth_type)


class AuthManager(object):
    """
    Singleton AuthManager that manages authentication strategy for
    HTTP requests.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(AuthManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Only initialize once
        if not hasattr(self, 'strategy'):
            self.strategy = None

    def set_strategy(self, strategy):
        """Set the authentication strategy (expects a strategy instance)."""
        self.strategy = strategy

    def get_key(self):
        if self.strategy is None:
            raise RuntimeError('No authentication strategy set!')
        return self.strategy.get_key()


# Singleton instance used throughout the codebase
Authentication = AuthManager()
