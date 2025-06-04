import argparse
import configparser
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

id_width = int(config['display']['id_width'])
hostname_width = int(config['display']['hostname_width'])
server_name_width = int(config['display']['server_name_width'])

default_interval = int(config['polling']['interval'])
default_timeout = int(config['polling']['timeout'])

base_url = str(config['urls']['base_url'])
get_agent_lists_url = str(config['urls']['get_agent_lists'])
poll_request_url = str(config['urls']['poll_request'])
send_command_url = str(config['urls']['send_command'])


def truncate(text: str, max_length: int) -> str:
    """Truncate text to fit max_length with ellipsis if needed."""
    return text if len(text) <= max_length else text[:max_length - 3] + '...'


def list_agents(url: Optional[str] = None) -> None:
    """
    List active agents as a formatted table, truncating long values.
    """
    if url is None:
        url = base_url.rstrip('/') + '/' + send_command_url.lstrip('/')
    print('Available agents:')
    print(
        f"{'ID':<{id_width}} {'Hostname':<{hostname_width}} "
        f"{'Server Name':<{server_name_width}}"
    )
    print('-' * (id_width + hostname_width + server_name_width + 2))

    # TODO: replace with actual url
    response = requests.get(url)
    agents = response.json()

    for agent in agents:
        id_str = str(agent['id'])
        hostname = truncate(agent['hostname'], hostname_width)
        server_name = truncate(agent.get('server_name', ''), server_name_width)

        print(
            f'{id_str:<{id_width}} {hostname:<{hostname_width}} '
            f'{server_name:<{server_name_width}}'
        )


def send_command(agent_hostname: str, command: str) -> None:
    """
    Send a command to a selected agent via POST 'commands'
    """
    pass


def poll_result(
    command_id: int,
    interval: int = 5,
    timeout: int = 30,
    username: Optional[str] = None,
    password: Optional[str] = None,
    url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    if url is None:
        url = base_url.rstrip('/') + '/' + poll_request_url.lstrip('/')
    payload = {'id': command_id}
    start_time = time.time()

    auth = (username, password) if username and password else None
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    while True:
        try:
            response = requests.patch(
                url, json=payload, auth=auth, headers=headers
            )
            response.raise_for_status()
            data = response.json()

            if data.get('result') is not None or data.get('status') == 'done':
                return data

            if time.time() - start_time > timeout:
                print(f'Timeout after {timeout} seconds.')
                return data

            print('Waiting for result...')
            time.sleep(interval)

        except requests.RequestException as e:
            print(f'Request failed: {e}')
            return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            'CLI for interaction with Django Controller '
            'to trigger commands on agents.'
        )
    )
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('agents', help='List active agents')

    send_parser = subparsers.add_parser('send', help='Send command to agent')
    send_parser.add_argument('hostname', help="Agent's hostname")
    send_parser.add_argument('command', help='Command to send to agent')

    poll_parser = subparsers.add_parser('poll', help='Poll result of command')
    poll_parser.add_argument('id', help='Command ID', type=int)
    poll_parser.add_argument(
        '--username', help='Username', type=str, required=True
    )
    poll_parser.add_argument(
        '--password', help='Password', type=str, required=True
    )

    args = parser.parse_args()

    if args.command == 'agents':
        list_agents()
    elif args.command == 'send':
        send_command(args.hostname, args.command)
    elif args.command == 'poll':
        poll_result(args.id, username=args.username, password=args.password)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
