from __future__ import print_function

import base64
import logging
import os
import subprocess
import threading
import time

import dotenv

from agents.smtp.smtp import SMTPAgent


def fetch(agent, credentials, interval=5, stop=None):
    """
    Fetch worker proceeds as follows:

        - Send GET request to controller to fetch the first pending
          command
        - Add command to Queue if it's allowed on the server
        - Wait
    """
    while not (stop and stop.is_set()):
        command = agent.fetch_command_from_controller(
            Authorization='Basic %s' % credentials
        )

        if command:
            agent.maybe_add_to_queue(command)

        time.sleep(interval)


def execute(agent, max_exec, stop):
    """
    Execute worker proceeds as follows:

        - Call Queue.get() (block until an item is available)
        - Execute command on the server and log status
        - Communicate that the item has been processed
    """
    for _ in range(max_exec):
        command = agent.queue.get()

        if command:
            # Start the process
            proc = subprocess.Popen(
                command['command'],
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = proc.communicate()
            output = stdout.decode('utf-8') + stderr.decode('utf-8')

            logging.info(
                'Command %s finished with status %s' % (
                    command['command'], proc.returncode
                )
            )
            logging.info('Command output: %s' % output)

        agent.queue.task_done()

    stop.set()


if __name__ == '__main__':
    dotenv.load_dotenv()

    credentials = (
        '%s:%s' % (os.getenv('DJANGO_USER'), os.getenv('DJANGO_PASSWORD'))
    ).encode('utf-8')
    credentials = base64.b64encode(credentials).decode('utf-8')

    agent = SMTPAgent.from_config_file()
    agent.collect_server_metadata()

    agent.hostname = 'test-smtp-server'

    max_exec = 5
    stop = threading.Event()

    fetcher = threading.Thread(
        target=fetch, args=(agent, credentials), kwargs={'stop': stop}
    )
    executor = threading.Thread(target=execute, args=(agent, max_exec, stop))

    fetcher.start()
    executor.start()

    executor.join()
    fetcher.join()

    logging.info('Threads finished executing %d commands' % max_exec)
