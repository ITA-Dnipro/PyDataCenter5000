import base64
import codecs
import json
import os
import re
import time


def ensure_directory_exists(path):
    """Ensure the parent directory for the given file path exists."""
    try:
        dir_path = os.path.dirname(path)
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
    except Exception as e:
        raise IOError('Failed to create directory for path %s: %s' % (path, e))


def write_to_file(path, content, logger=None):
    """Write content to a file, creating parent directories as needed."""
    try:
        ensure_directory_exists(path)
        with codecs.open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        if logger:
            logger.error('Failed to write to file %s: %s' % (path, e))
        raise IOError('Failed to write to file %s: %s' % (path, e))


def read_from_file(path, logger=None):
    """Read and return the content of a file."""
    try:
        if os.path.exists(path):
            with codecs.open(path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        if logger:
            logger.error('Failed to read from file %s: %s' % (path, e))
        raise IOError('Failed to read from file %s: %s' % (path, e))
    return None


def is_jwt(token):
    """Basic pattern check to see if the string looks like a JWT."""
    try:
        jwt_pattern = re.compile(
            r'^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$'
        )
        return bool(jwt_pattern.match(token))
    except Exception:
        return False


def decode_jwt(token):
    """Decode the payload part of a JWT (without verifying signature)."""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding = '=' * (4 - len(payload) % 4)
        payload += padding
        decoded = base64.b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return {}


def is_valid_token(token):
    """Check if token is JWT and not expired."""
    try:
        if not is_jwt(token):
            return False
        payload = decode_jwt(token)
        exp = payload.get('exp')
        if exp and int(exp) > int(time.time()):
            return True
    except Exception:
        pass
    return False
