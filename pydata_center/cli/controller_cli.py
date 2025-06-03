import argparse
import configparser
import os

import requests

config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config = configparser.ConfigParser()
config.read(config_path)

id_width = int(config['display']['id_width'])
hostname_width = int(config['display']['hostname_width'])
server_name_width = int(config['display']['server_name_width'])

default_interval = int(config['polling']['interval'])
default_timeout = int(config['polling']['timeout'])


def truncate(text, max_length):
    """Truncate text to fit max_length with ellipsis if needed."""
    return text if len(text) <= max_length else text[:max_length - 3] + '...'


def list_agents(url: str = None):
    """
    List active agents as a formatted table, truncating long values.
    """
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


def send_command(agent_hostname, command):
    """
    Send a command to a selected agent via POST 'commands'
    """
    pass


def poll_result(
        command_id, interval=default_interval, timeout=default_timeout
):
    """
    Poll for the result from 'submit_command_result'
    """
    pass


def main():
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

    args = parser.parse_args()

    if args.command == 'agents':
        list_agents()
    elif args.command == 'send':
        send_command(args.hostname, args.command)
    elif args.command == 'poll':
        poll_result(args.id)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
