from __future__ import print_function

import base64
import logging
import os
import subprocess

import dotenv

from agents_infra.agents import SMTPAgent
from agents_infra.agents.exceptions import BadSubprocessReturnCode
from agents_infra.agents.supervisor import AgentSupervisor
from agents_infra.agents.utils import make_callback


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
    agent.evaluate_identity()

    supervisor = AgentSupervisor(agent)

    def fetch_command(credentials, **kwargs):
        data = agent.fetch_command_from_controller(
            Authorization='Basic %s' % credentials, **kwargs
        )

        if data:
            logging.info('Data received - maybe adding command to queue')

            agent.maybe_add_command_to_queue(data)

    def execute_command():
        logging.info('Waiting for commands')

        command_history = None

        while True:
            command_history = agent.get_command_from_queue()

            if command_history:
                logging.warning(
                    'Command %s received' % command_history.command
                )
                break

            supervisor.sleep(0.1)

        try:
            proc = subprocess.Popen(
                command_history.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = proc.communicate()
            output = stdout.decode('utf-8') + stderr.decode('utf-8')

            if proc.returncode != 0:
                raise BadSubprocessReturnCode(
                    'Command failed with return code %d' % proc.returncode
                )

            logging.info('Command %s succeeded' % command_history.command)
            logging.info('Command output: %s...[truncated]' % output[:300])
        except OSError as e:
            logging.error(
                'Subprocess failed due to error: %s' % str(e),
                exc_info=True,
            )

    def on_timeout(idx, retry, credentials):
        agent.post_data(
            url='server/status/',
            payload=agent.status_to_dict(),
            to_controller=True,
            Authorization='Basic %s' % credentials,
        )

    on_timeout_callback = make_callback(on_timeout, credentials=credentials)

    supervisor.schedule(fetch_command, max_delay=5, credentials=credentials)
    supervisor.schedule(
        execute_command,
        max_retries=2,
        max_delay=5,
        timeout=2,
        on_timeout=on_timeout_callback,
    )

    supervisor.schedule_exit(min_delay=0.1, max_delay=1)

    supervisor.start()


if __name__ == '__main__':
    main()
