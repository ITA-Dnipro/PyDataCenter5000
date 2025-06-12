from __future__ import print_function

import base64
import logging
import os
import subprocess
import time

import coro
import dotenv

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
    agent.collect_server_metadata()

    supervisor = AgentSupervisor(agent)

    def fetch_command(credentials, interval=5, **kwargs):
        data = agent.fetch_command_from_controller(
            Authorization='Basic %s' % credentials, **kwargs
        )

        if data:
            logging.info('Data received - maybe adding command to queue')

            agent.maybe_add_to_queue(data)

        supervisor.sleep(interval)

    retries = [0]

    def execute_command(timeout, interval=5):
        command_history = None

        start = time.time()

        while True:
            if time.time() - start > timeout:
                logging.warning('No command received in allocated time')
                break

            if len(agent.queue) > 0:
                command_history = agent.queue.pop()
                break

            supervisor.sleep(0.1)

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

        retries[0] += 1

        supervisor.sleep(interval)

    supervisor.schedule(fetch_command, credentials=credentials)
    supervisor.schedule(execute_command, timeout=10)

    supervisor.schedule_exit(stop_condition=lambda: retries[0] >= 3)

    supervisor.start()


if __name__ == '__main__':
    main()
