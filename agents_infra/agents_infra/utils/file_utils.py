import base64
import binascii
import codecs
import json
import logging
import os
import re
import time

# Compile JWT regex once at module load for efficiency
_JWT_PATTERN = re.compile(
    r'^[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+$'
)

logger = logging.getLogger(__name__)


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
            logger.error(
                'Failed to write to file %s: %s', path, e, exc_info=True
            )
        raise IOError('Failed to write to file %s: %s' % (path, e))


def read_from_file(path, logger=None, chunk_size=4096):
    """
    Read and return the content of a file.

    Reads the file in chunks to handle large files and uses 'utf-8' encoding.
    Decoding errors are handled by replacing invalid chars.

    Returns None if file does not exist.
    """
    try:
        if not os.path.exists(path):
            return None
        content = []
        with open(path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                content.append(chunk.decode(
                    'utf-8', errors='replace'
                ))
        return ''.join(content)
    except Exception as e:
        if logger:
            logger.error(
                'Failed to read from file %s: %s',
                path,
                e,
                exc_info=True
            )
        raise IOError('Failed to read from file %s: %s' % (path, e))


def is_jwt(token):
    """Basic pattern check to see if the string looks like a JWT."""
    try:
        return bool(_JWT_PATTERN.match(token))
    except Exception:
        return False


def decode_jwt(token):
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        padding_len = -len(payload) % 4
        payload += '=' * padding_len
        decoded_bytes = base64.urlsafe_b64decode(payload)
        return json.loads(decoded_bytes)
    except AttributeError:
        # token not a string or None
        logger.debug('Token is not a string: %r', token)
    except binascii.Error as e:
        logger.debug('Base64 decoding error: %s', e)
    except (json.JSONDecodeError, ValueError) as e:
        # JSON decoding error or ValueError in older versions
        logger.debug('JSON decoding error: %s', e)
    except Exception as e:
        logger.debug('Unexpected error decoding JWT: %s', e)
    return {}


def is_valid_token(token):
    try:
        if not is_jwt(token):
            logger.debug('Token does not match JWT pattern.')
            return False
        payload = decode_jwt(token)
        exp = payload.get('exp')
        if exp is None:
            logger.debug('Token missing "exp" claim.')
            return False
        exp_int = int(exp)
        current_time = int(time.time())
        if exp_int > current_time:
            return True
        else:
            logger.debug(
                'Token expired at %d, current time is %d.',
                exp_int,
                current_time
            )
    except (ValueError, TypeError) as e:
        logger.debug('Invalid "exp" claim in token: %s', e)
    except Exception as e:
        logger.debug(
            'Unexpected error validating token: %s', e)
    return False
