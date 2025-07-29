import logging
import os

import agents_infra.agents

logger = logging.getLogger(__name__)


class TokenStorage(object):
    """
    Handles persistent storage and retrieval of agent authentication tokens.

    Token files are stored in a writable directory resolved from:
    1. A custom path, if valid and writable.
    2. The local agents module directory.
    3. A fallback system path (/var/lib/agent/).
    """

    FALLBACK_DIR = '/var/lib/agent'

    def __init__(self, server_name):
        """
        Args:
            server_name (str): Unique name for the agent used as
            the token filename.
        """
        self.server_name = server_name

    def get_token_file_path(self, custom_path=None):
        """
        Resolves the file path for storing or retrieving the token.

        Priority:
        1. Use the given custom path if it exists and is writable.
        2. Use the agents module directory if writable.
        3. Fallback to /var/lib/agent/

        Args:
            custom_path (str, optional):
            User-provided full file path for token.

        Returns:
            str: Full file path for storing the token.
        """
        if custom_path:
            if os.path.exists(custom_path) and os.access(custom_path, os.W_OK):
                return custom_path
            else:
                logger.warning(
                    'Custom path %s is not usable, falling back.',
                    custom_path
                )

        agents_path = os.path.dirname(agents_infra.agents.__file__)
        if os.path.exists(agents_path) and os.access(agents_path, os.W_OK):
            tokens_dir = os.path.join(agents_path, 'tokens')
            if not os.path.exists(tokens_dir):
                try:
                    os.makedirs(tokens_dir)
                except OSError as e:
                    logger.warning(
                        'Failed to create tokens directory %s: %s',
                        tokens_dir, e
                    )
                    return os.path.join(
                        self.FALLBACK_DIR,
                        '%s.token' % self.server_name
                    )
            return os.path.join(tokens_dir, '%s.token' % self.server_name)

        return os.path.join(self.FALLBACK_DIR, '%s.token' % self.server_name)

    def load_token(self, path=None):
        """
        Load a token from storage.

        Args:
            path (str, optional): Custom token file path.

        Returns:
            str or None: Token string if found, else None.
        """
        full_path = self.get_token_file_path(path)
        if os.path.exists(full_path):
            try:
                with open(full_path, 'r') as f:
                    return f.read().strip()
            except IOError as e:
                logger.warning(
                    'Could not read token file %s: %s',
                    full_path, e)
        return None

    def save_token(self, token, path=None):
        """
        Save a token to the storage file.

        Args:
            token (str): Token string to save.
            path (str, optional): Custom file path to store the token.
        """
        full_path = self.get_token_file_path(path)
        dir_path = os.path.dirname(full_path)
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError as e:
                logger.error(
                    'Failed to create directory %s for token: %s',
                    dir_path, e
                )
                raise

        try:
            with open(full_path, 'w') as f:
                f.write(token)
        except IOError as e:
            logger.error(
                'Failed to write token to file %s: %s',
                full_path, e
            )
            raise
