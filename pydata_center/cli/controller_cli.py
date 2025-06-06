import argparse
import configparser
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests
from dotenv import load_dotenv, set_key

# === Logging setup ===
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# === Config setup ===
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

id_width = int(config.get('display', 'id_width', fallback='10'))
hostname_width = int(config.get('display', 'hostname_width', fallback='20'))
server_name_width = int(
    config.get('display', 'server_name_width', fallback='25')
)

default_interval = int(config.get('polling', 'interval', fallback='5'))
default_timeout = int(config.get('polling', 'timeout', fallback='30'))

base_url = config.get(
    'urls', 'base_url', fallback='http://127.0.0.1:8000/api'
)
get_agent_lists_url = config.get(
    'urls', 'get_agent_lists', fallback='v1/agents/'
)
send_command_url = config.get(
    'urls', 'send_command', fallback='v1/commands/'
)
poll_request_url = config.get(
    'urls', 'poll_request', fallback='v1/command/result/'
)

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)


# === Helpers ===
def resolve_auth(
    username: Optional[str], password: Optional[str]
) -> Optional[Tuple[str, str]]:
    if username and password:
        return username, password
    return get_auth_from_env()


def login(username: str, password: str) -> None:
    """
    Save credentials to .env file.
    """
    set_key(str(env_path), 'USERNAME', username)
    set_key(str(env_path), 'PASSWORD', password)
    logger.info('Login successful. Credentials saved.')


def get_auth_from_env() -> Optional[Tuple[str, str]]:
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')
    if username and password:
        return username, password
    return None


def truncate(text: str, max_length: int) -> str:
    """Truncate text to fit max_length with ellipsis if needed."""
    return text if len(text) <= max_length else text[:max_length - 3] + '...'


# === Commands ===
def list_agents(
    url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """
    List active agents as a formatted table, truncating long values.
    Requires authentication.
    """
    url = url or base_url.rstrip('/') + '/' + get_agent_lists_url.lstrip('/')
    auth = resolve_auth(username, password)

    if not auth:
        logger.error("You must login first using the 'login' command.")
        return

    try:
        response = requests.get(
            url,
            headers={'Accept': 'application/json'},
            auth=auth
        )
        response.raise_for_status()
        agents = response.json()

        header = (
            f"{'ID':<{id_width}} "
            f"{'Hostname':<{hostname_width}} "
            f"{'Server Name':<{server_name_width}}"
        )
        separator = '-' * (id_width + hostname_width + server_name_width + 2)

        logger.info('Available agents:')
        logger.info(header)
        logger.info(separator)

        for agent in agents:
            id_str = str(agent['id'])
            hostname = truncate(agent['hostname'], hostname_width)
            server_name = truncate(
                agent.get('server_name', ''), server_name_width
            )

            logger.info(
                f'{id_str:<{id_width}} {hostname:<{hostname_width}} '
                f'{server_name:<{server_name_width}}'
            )
    except requests.RequestException as e:
        logger.error(f'Failed to retrieve agents: {e}')


def send_command(
    agent_hostname: str,
    command: str,
    username: Optional[str] = None,
    password: Optional[str] = None,
    url: Optional[str] = None,
) -> Optional[int]:
    """
    Send a command to a selected agent via POST and return the command ID.
    """
    url = url or base_url.rstrip('/') + '/' + send_command_url.lstrip('/')
    auth = resolve_auth(username, password)

    if not auth:
        logger.error("You must login first using the 'login' command.")
        return None

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
            logger.info(
                f'Command sent to {agent_hostname} successfully. '
                f'Command ID: {command_id}'
            )
            return command_id
        logger.warning('Command sent, but no command ID returned.')
    except requests.HTTPError as http_err:
        logger.error(f'HTTP error occurred: {http_err}')
    except requests.RequestException as req_err:
        logger.error(f'Request failed: {req_err}')
    except Exception as err:
        logger.error(f'Unexpected error: {err}')

    return None


def poll_result(
    command_id: int,
    interval: int = 5,
    timeout: int = 30,
    username: Optional[str] = None,
    password: Optional[str] = None,
    url: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    url = url or base_url.rstrip('/') + '/' + poll_request_url.lstrip('/')
    auth = resolve_auth(username, password)

    if not auth:
        logger.error("You must login first using the 'login' command.")
        return None

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    payload = {'id': command_id}
    start_time = time.time()

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
                logger.warning(f'Timeout after {timeout} seconds.')
                return data

            logger.info('Waiting for result...')
            time.sleep(interval)

        except requests.RequestException as e:
            logger.error(f'Request failed: {e}')
            return None


# === CLI handlers ===
def handle_login(args):
    login(args.username, args.password)


def handle_agents():
    auth = get_auth_from_env()
    if not auth:
        logger.error("You must login first using the 'login' command.")
        return
    list_agents(username=auth[0], password=auth[1])


def handle_send(args):
    auth = get_auth_from_env()
    if not auth:
        logger.error("You must login first using the 'login' command.")
        return
    command_id = send_command(
        args.hostname,
        args.cmd,
        username=auth[0],
        password=auth[1]
    )
    if command_id:
        logger.info(f'Use this ID to poll the result: {command_id}')
        if args.poll:
            result = poll_result(
                command_id,
                interval=default_interval,
                timeout=default_timeout,
                username=auth[0],
                password=auth[1],
            )
            if result:
                logger.info(
                    f"Result: {result.get('result', '[no result returned]')}"
                )


def handle_poll(args):
    auth = get_auth_from_env()
    if not auth:
        logger.error("You must login first using the 'login' command.")
        return
    result = poll_result(args.id, username=auth[0], password=auth[1])
    if result:
        logger.info(f"Result: {result.get('result', '[no result returned]')}")


# === Main ===
def main() -> None:
    parser = argparse.ArgumentParser(
        description='CLI to interact with agents via Django Controller.'
    )
    subparsers = parser.add_subparsers(dest='command')

    subparsers.add_parser('agents', help='List active agents')

    login_parser = subparsers.add_parser(
        'login', help='Login and store credentials'
    )
    login_parser.add_argument('--username', required=True, help='Username')
    login_parser.add_argument('--password', required=True, help='Password')

    send_parser = subparsers.add_parser(
        'send', help='Send command to agent'
    )
    send_parser.add_argument('hostname', help="Agent's hostname")
    send_parser.add_argument('cmd', help='Command to send to agent')
    send_parser.add_argument(
        '--poll',
        help='Poll for result after sending',
        action='store_true'
    )

    poll_parser = subparsers.add_parser(
        'poll', help='Poll result of command'
    )
    poll_parser.add_argument('id', help='Command ID', type=int)

    args = parser.parse_args()

    if args.command == 'login':
        handle_login(args)
    elif args.command == 'agents':
        handle_agents()
    elif args.command == 'send':
        handle_send(args)
    elif args.command == 'poll':
        handle_poll(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
