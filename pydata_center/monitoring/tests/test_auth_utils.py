import datetime

import jwt
import pytest
from django.conf import settings
from monitoring.utils import decode_agent_jwt, generate_agent_token
from rest_framework.exceptions import AuthenticationFailed


@pytest.fixture
def agent_info():
    return {'agent_id': 42, 'agent_name': 'test-agent'}


def test_generate_and_decode_token(agent_info):
    """Token generated should decode back to original payload."""
    token = generate_agent_token(
        agent_info['agent_id'],
        agent_info['agent_name']
    )
    payload = decode_agent_jwt(token)

    assert payload['agent_id'] == agent_info['agent_id']
    assert payload['name'] == agent_info['agent_name']
    assert 'iat' in payload


def test_decode_invalid_token_raises():
    """Decoding a malformed token should raise AuthenticationFailed."""
    with pytest.raises(AuthenticationFailed) as exc:
        decode_agent_jwt('this.is.not.a.valid.token')
    assert 'Invalid token' in str(exc.value)


def test_expired_token_raises(agent_info, monkeypatch):
    """Decoding an expired token should raise AuthenticationFailed."""
    # Generate an expired token
    expired_payload = {
        'agent_id': agent_info['agent_id'],
        'name': agent_info['agent_name'],
        'iat': int(datetime.datetime.utcnow().timestamp()),
        'exp': datetime.datetime.utcnow() - datetime.timedelta(seconds=1)
    }

    expired_token = jwt.encode(
        expired_payload,
        settings.SECRET_KEY,
        algorithm='HS256'
    )

    if isinstance(expired_token, bytes):
        expired_token = expired_token.decode()

    with pytest.raises(AuthenticationFailed) as exc:
        decode_agent_jwt(expired_token)
    assert 'Token has expired' in str(exc.value)
