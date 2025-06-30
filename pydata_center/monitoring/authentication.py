import hashlib

import jwt
from django.conf import settings
from rest_framework import authentication, exceptions

from .models import Agent


class AgentTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        print(7)
        auth_header = authentication.get_authorization_header(request).split()
        print(auth_header)
        print(auth_header[0].lower())
        if not auth_header or auth_header[0].lower() != b'bearer':
            print(8)
            return None

        if len(auth_header) != 2:
            print(9)
            raise exceptions.AuthenticationFailed('Invalid token header.')

        token = auth_header[1].decode()
        print(token)
        # Validate JWT format and decode
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=['HS256']
            )
            agent_id = payload.get('agent_id')
            print('ID')
            print(agent_id)
            if not agent_id:
                raise exceptions.AuthenticationFailed('Invalid token payload.')
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed('Invalid token.')

        # Hash the provided token and match with stored hash
        token_hash = hashlib.sha512(token.encode()).hexdigest()

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
