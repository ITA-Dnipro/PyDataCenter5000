import os
import sys
import time
import logging

sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../..')
    )
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
        print('Usage: python run_agent.py <agent_name>')
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

        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            agent_name,
            'config.ini'
        )
        config_path = os.path.abspath(config_path)

        if os.path.exists(config_path):
            print('Loading agent from config file: %s' % config_path)
            agent = agent_class.from_config_file(filename=config_path)
        else:
            print('No config file found; using default constructor.')
            agent = agent_class()

        try:
            agent.setup_logging()
        except AttributeError:
            pass

        print('Agent initialized. Starting health loop...')
        agent.collect_server_metadata()
        while True:
            time.sleep(1)

    except Exception as e:
        print('Error: %s' % str(e))
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

