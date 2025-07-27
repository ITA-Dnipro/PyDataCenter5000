import hashlib

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from .models import Agent


class AgentTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        try:
            auth_header = (authentication.get_authorization_header(request)
                           .decode('utf-8').split())
        except UnicodeDecodeError:
            raise exceptions.AuthenticationFailed(
                'Invalid encoding in Authorization header.'
            )

        if not auth_header or auth_header[0].lower() != 'bearer':
            return None

        if len(auth_header) != 2:
            raise exceptions.AuthenticationFailed(
                'Invalid token header format.'
            )

        token = auth_header[1]

        # Decode and validate JWT
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token.')

        agent_id = payload.get('agent_id')
        if not agent_id:
            raise exceptions.AuthenticationFailed(
                'Token payload missing agent ID.'
            )

        # Hash token and compare to stored value
        token_hash = hashlib.sha512(token.encode('utf-8')).hexdigest()

        try:
            agent = Agent.objects.get(
                id=agent_id,
                token_hash=token_hash,
                is_active=True
            )
        except Agent.DoesNotExist:
            raise exceptions.AuthenticationFailed(
                'Token does not match any active agent.'
            )

        return (agent, None)
