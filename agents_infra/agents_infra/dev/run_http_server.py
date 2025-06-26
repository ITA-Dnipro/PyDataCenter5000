import logging
import os
import sys
import time

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../..')
    )
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def main():
    """
    Developer utility to run an agent with health server loop.

    Usage:
        python run_agent.py <agent_name>

    Loads agent config from agents/<agent_name>/config.ini if present,
    starts health server and runs indefinitely.
    """
    if len(sys.argv) != 2:
        logging.error('Usage: python run_agent.py <agent_name>')
        sys.exit(1)

    agent_name = sys.argv[1]

    try:
        # Dynamically import: agents.dns.dns -> DNSAgent
        module = __import__(
            'agents.%s.%s' % (agent_name, agent_name), fromlist=['']
        )

        if agent_name.lower() == 'web':
            agent_class = getattr(module, 'WebAgent')
        else:
            agent_class = getattr(module, agent_name.upper() + 'Agent')

        config_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), '..', agent_name, 'config.ini'
            )
        )

        if os.path.exists(config_path):
            logging.info('Loading agent from config file: %s' % config_path)
            agent = agent_class.from_config_file(filename=config_path)
        else:
            logging.warning('No config file found; using default constructor.')
            agent = agent_class()

        try:
            agent.setup_logging()
        except AttributeError:
            logging.debug('Agent does not implement setup_logging().')

        logging.info('Agent initialized. Starting health loop...')
        agent.collect_server_metadata()
        while True:
            time.sleep(1)

    except Exception as e:
        logging.exception('Error while running agent: %s' % e)
        sys.exit(1)


if __name__ == '__main__':
    main()
