import argparse
import configparser
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv, set_key

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


env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


def login(username: str, password: str) -> None:
    """
    Save credentials to .env file.
    """
    set_key(str(env_path), 'USERNAME', username)
    set_key(str(env_path), 'PASSWORD', password)
    print('Login successful. Credentials saved.')


def get_auth_from_env() -> Optional[Tuple[str, str]]:
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')
    if username and password:
        return username, password
    return None


def truncate(text: str, max_length: int) -> str:
    """Truncate text to fit max_length with ellipsis if needed."""
    return text if len(text) <= max_length else text[:max_length - 3] + '...'


def list_agents(
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None
) -> None:
    """
    List active agents as a formatted table, truncating long values.
    Requires authentication.
    """
    if url is None:
        url = base_url.rstrip('/') + '/' + get_agent_lists_url.lstrip('/')

    if username is None or password is None:
        auth = get_auth_from_env()
        if not auth:
            print("You must login first using the 'login' command.")
            return
        username, password = auth

    headers = {
        'Accept': 'application/json',
    }

    try:
        response = requests.get(
            url, headers=headers, auth=(username, password)
        )
        response.raise_for_status()
        agents = response.json()

        print('Available agents:')
        print(
            f"{'ID':<{id_width}} {'Hostname':<{hostname_width}} "
            f"{'Server Name':<{server_name_width}}"
        )
        print('-' * (id_width + hostname_width + server_name_width + 2))

        for agent in agents:
            id_str = str(agent['id'])
            hostname = truncate(agent['hostname'], hostname_width)
            server_name = truncate(
                agent.get('server_name', ''), server_name_width
            )

            print(
                f'{id_str:<{id_width}} {hostname:<{hostname_width}} '
                f'{server_name:<{server_name_width}}'
            )
    except requests.RequestException as e:
        print(f'Failed to retrieve agents: {e}')


def send_command(
    agent_hostname: str,
    command: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    url: Optional[str] = None
) -> Optional[int]:
    """
    Send a command to a selected agent via POST and return the command ID.
    """
    if url is None:
        url = base_url.rstrip('/') + '/' + send_command_url.lstrip('/')
    auth = (username, password) if username and password else None
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    data = {
        'hostname': agent_hostname,
        'command': command,
    }

    try:
        response = requests.post(url, json=data, headers=headers, auth=auth)
        response.raise_for_status()
        result = response.json()

        command_id = result.get('id') or result.get('command_id')
        if command_id is not None:
            print(
                f'Command sent to {agent_hostname} successfully. '
                f'Command ID: {command_id}'
            )
            return command_id
        else:
            print('Command sent, but no command ID returned.')
            return None

    except requests.HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')
    except requests.RequestException as req_err:
        print(f'Request failed: {req_err}')
    except Exception as err:
        print(f'Unexpected error: {err}')

    return None


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

    login_parser = subparsers.add_parser(
        'login', help='Login and store credentials'
    )
    login_parser.add_argument('--username', required=True, help='Username')
    login_parser.add_argument('--password', required=True, help='Password')

    send_parser = subparsers.add_parser('send', help='Send command to agent')
    send_parser.add_argument('hostname', help="Agent's hostname")
    send_parser.add_argument('cmd', help='Command to send to agent')
    send_parser.add_argument(
        '--poll', help='Poll for result after sending', action='store_true'
    )

    poll_parser = subparsers.add_parser('poll', help='Poll result of command')
    poll_parser.add_argument('id', help='Command ID', type=int)

    args = parser.parse_args()

    if args.command == 'login':
        login(args.username, args.password)

    elif args.command == 'agents':
        auth = get_auth_from_env()
        if not auth:
            print("You must login first using the 'login' command.")
            return
        list_agents(username=auth[0], password=auth[1])

    elif args.command == 'send':
        auth = get_auth_from_env()
        if not auth:
            print("You must login first using the 'login' command.")
            return
        command_id = send_command(
            args.hostname,
            args.cmd,
            username=auth[0],
            password=auth[1]
        )
        if command_id:
            print(f'Use this ID to poll the result: {command_id}')
            if args.poll:
                result = poll_result(
                    command_id,
                    interval=default_interval,
                    timeout=default_timeout,
                    username=auth[0],
                    password=auth[1]
                )
                if result:
                    print(
                        'Result:',
                        result.get('result', '[no result returned]')
                    )

    elif args.command == 'poll':
        auth = get_auth_from_env()
        if not auth:
            print("You must login first using the 'login' command.")
            return
        result = poll_result(
            args.id,
            username=auth[0],
            password=auth[1]
        )
        if result:
            print('Result:', result.get('result', '[no result returned]'))

    else:
        parser.print_help()


if __name__ == '__main__':
    main()
