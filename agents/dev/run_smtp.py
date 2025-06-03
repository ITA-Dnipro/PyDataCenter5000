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
        help='Comma-separated list of processes'
    )

    args = parser.parse_args()

    processes = args.processes.split(',') if args.processes else None

    agent = SMTPAgent(
        port=args.port,
        processes=processes,
        controller_url=args.controller_url
    )
    agent.setup_logging()

    agent.collect_server_metadata()

    print(json.dumps(json.loads(agent.status_to_json()), indent=2))


if __name__ == '__main__':
    main()
