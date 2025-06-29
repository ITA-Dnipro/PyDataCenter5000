from __future__ import print_function

import base64
import logging
import os
import subprocess
import threading
import time

import dotenv
import Queue
from agents_infra.agents.smtp.smtp import SMTPAgent


def fetch(agent, credentials, interval=5, stop=None):
    """
    Fetch worker proceeds as follows:

        - Send GET request to controller to fetch the first pending
          command
        - Add command to Queue if it's allowed on the server
        - Wait
    """
    while not (stop and stop.is_set()):
        data = agent.fetch_command_from_controller(
            Authorization='Basic %s' % credentials
        )

        if data:
            agent.maybe_add_to_queue(data)

        time.sleep(interval)


def execute(agent, max_exec, stop):
    """
    Execute worker proceeds as follows:

        - Call Queue.get() (block until an item is available)
        - Execute command on the server and log status
        - Communicate that the item has been processed
    """
    for _ in range(max_exec):
        try:
            command_history = agent.queue.get(timeout=10)
        except Queue.Empty:
            logging.warning('No command received in allocated time')
            break

        if command_history:
            try:
                # Start the process
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

        agent.queue.task_done()

    stop.set()


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

    agent.hostname = 'test-smtp-server'

    max_exec = 1
    stop = threading.Event()

    fetcher = threading.Thread(
        target=fetch, args=(agent, credentials), kwargs={'stop': stop}
    )
    executor = threading.Thread(target=execute, args=(agent, max_exec, stop))

    try:
        fetcher.start()
        executor.start()

        executor.join()
        fetcher.join()
    except KeyboardInterrupt:
        logging.info('Interrupted. Exiting...')

        stop.set()

        # Let threads clean up
        fetcher.join()
        executor.join()

    logging.info('Threads finished executing')


if __name__ == '__main__':
    main()
