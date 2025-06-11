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

    def fetch_command(credentials, **kwargs):
        data = agent.fetch_command_from_controller(
            Authorization='Basic %s' % credentials, **kwargs
        )

        if data:
            agent.maybe_add_to_queue(data)

    nexec = 0

    def execute_command(timeout):
        nonlocal nexec

        command_history = None

        while True:
            start = time.time()

            if agent.queue:
                command_history = agent.queue.pop(0)

            if time.time() - start > timeout:
                logging.warning('No command received in allocated time')
                break

        if command_history:
            try:
                proc = subprocess.Popen(
                    command_history.command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )

                stdout, stderr = proc.communicate()
                output = stdout.decode('utf-8') + stderr.decode('utf-8')

                nexec += 1

                logging.info(
                    'Command %s finished with status %s' % (
                        command_history.command, proc.returncode
                    )
                )
                logging.info('Command output: %s' % output)
            except Exception as e:
                logging.error(
                    'Failed to execute command '
                    '%s due to error: %s' % (command_history.command, str(e)),
                    exc_info=True,
                )

    supervisor.schedule(fetch_command, interval=10, credentials=credentials)
    supervisor.schedule(execute_command, interval=10, timeout=5)

    supervisor.schedule_exit(stop_condition=lambda: nexec >= 2, interval=10)

    supervisor.start()


if __name__ == '__main__':
    main()
