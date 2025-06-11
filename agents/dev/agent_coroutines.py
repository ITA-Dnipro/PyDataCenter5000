from __future__ import print_function

import base64
import logging
import os
import subprocess
import time

import dotenv
import Queue

from agents.smtp.smtp import SMTPAgent
from agents.supervisor import AgentSupervisor


def main():
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '../.env'
    )
    dotenv.load_dotenv(path)

    credentials = (
        '%s:%s' % (os.getenv('DJANGO_USER'), os.getenv('DJANGO_PASSWORD'))
    ).encode('utf-8')
    credentials = base64.b64encode(credentials).decode('utf-8')

    agent = SMTPAgent.from_config_file()

    supervisor = AgentSupervisor(agent)

    supervisor.schedule(agent.collect_server_metadata, 10)
    supervisor.schedule(agent.status_to_txt, 10)
    supervisor.schedule_exit()

    supervisor.start()


if __name__ == '__main__':
    main()
