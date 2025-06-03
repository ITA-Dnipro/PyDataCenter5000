import argparse


def list_agents():
    """
    List active agents.
    """
    pass


def send_command(agent_hostname, command):
    """
    Send a command to a selected agent via POST 'commands'
    """
    pass


def poll_result(command_id, interval=2, timeout=30):
    """
    Poll for the result from poll for the result from 'submit_command_result'
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
