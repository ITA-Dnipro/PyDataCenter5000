import hashlib

from rest_framework import authentication

from .helpers import raise_invalid_token
from .models import Agent
from .utils import decode_agent_jwt


class AgentTokenAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):

        try:
            auth_header = (
                authentication.get_authorization_header(request)
                .decode('utf-8')
                .split()
            )
        except UnicodeDecodeError:
            raise_invalid_token('Invalid encoding in Authorization header.')

        if not auth_header or auth_header[0].lower() != 'bearer':
            return None  # Let other authenticators try

        if len(auth_header) != 2:
            raise_invalid_token('Invalid token header format.')

        token = auth_header[1]

        payload = decode_agent_jwt(token)

        agent_id = payload.get('agent_id')
        if not agent_id:
            raise_invalid_token('Token payload missing agent ID.')

        token_hash = hashlib.sha512(token.encode('utf-8')).hexdigest()

        try:
            agent = Agent.objects.get(
                id=agent_id,
                token_hash=token_hash,
                is_active=True
            )
        except Agent.DoesNotExist:
            raise_invalid_token('Token does not match any active agent.')

        return (agent, None)
