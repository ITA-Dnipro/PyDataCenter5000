from __future__ import print_function

import argparse
import json

from agents.smtp.smtp import SMTPAgent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--host',
        default='127.0.0.1',
        help='SMTP server host'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=25,
        help='SMTP port'
    )
    parser.add_argument(
        '--controller-url',
        dest='controller_url',
        help='Controller URL'
    )
    parser.add_argument(
        '--processes',
        nargs='*',
        help=(
            'List of processes to check '
            '(e.g., --processes postfix exim sendmail)'
        )
    )
    parser.add_argument(
        '--pretty',
        action='store_true',
        help='Pretty-print the JSON output'
    )

    args = parser.parse_args()

    if not args.controller_url:
        parser.error(
            '--controller-url is required for communication with controller'
        )

    agent = SMTPAgent(
        port=args.port,
        processes=args.processes,
        controller_url=args.controller_url
    )
    agent.setup_logging()

    agent.collect_server_metadata()

    data = agent.status_to_json()
    if args.pretty:
        print(json.dumps(json.loads(data), indent=2))
    else:
        print(data)


if __name__ == '__main__':
    main()
