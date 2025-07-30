from __future__ import print_function

import base64
import sys
import json

from agents_infra.agents.dns.dns import DNSAgent
from agents_infra.exceptions import BadProcessReturnCode


def get_basic_auth_header(username, password):
    credentials = '%s:%s' % (username, password)
    encoded = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return 'Basic %s' % encoded


def main():
    username = 'admin'
    password = '1234'
    auth_header = get_basic_auth_header(username, password)

    try:
        agent = DNSAgent.from_config_file('agents_infra/agents/dns/config.ini')
        agent.config.name = 'dns_agent'

        agent.collect_server_metadata()

        print("🚀 Agent initialized:", agent.config.name)

        command_data = agent.get_data(
            url='command/fetch/?hostname=%s' % agent.hostname,
            to_controller=True,
            Authorization=auth_header,
        )

        if not command_data:
            print("⚠ No command data received from controller.")
            return

        print("📥 Command data received:", command_data)

        patch_url = 'command/result/%s/' % 12
        payload = {
            'status': 'done',
            'result': 'done'
        }
        response = agent.patch_data(
            patch_url, json.loads(json.dumps(payload)), Authorization=auth_header
        )

        print("🔁 PATCH sent. Response:", response)
        print("✔ Agent command processed and patched.")
    except Exception as e:
        print("🔥 Unhandled exception in main():", str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
