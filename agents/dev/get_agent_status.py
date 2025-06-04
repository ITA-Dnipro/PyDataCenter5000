import json
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
)


def main():
    """
    Developer utility to get agent status information.

    This script retrieves and displays the status of a specified agent.
    It outputs the agent's data in JSON format to stdout and writes logs
    to a text file using the agent's status_to_txt() method.

    Usage:
        python get_agent_status.py <agent_name>

    Args:
        None (uses sys.argv[1] for agent_name)

    Returns:
        None (prints JSON to stdout and writes logs to text file)
    """
    if len(sys.argv) != 2:
        print('Usage: python get_agent_status.py <agent_name>')
        sys.exit(1)

    agent_name = sys.argv[1]

    try:
        # Dynamically import agents.<agent_name>.<agent_name>
        module = __import__('agents.{0}.{0}'.format(agent_name), fromlist=[''])
        # Pick the right class name (e.g. ntp -> NTPAgent, web -> WebAgent)
        if agent_name.lower() == 'web':
            agent_class = getattr(module, 'WebAgent')
        else:
            agent_class = getattr(module, agent_name.upper() + 'Agent')

        # If there's a config.ini under agents/<agent_name>/config.ini
        config_path = os.path.join(
            os.path.dirname(__file__),
            agent_name,
            'config.ini'
        )

        if os.path.exists(config_path):
            print('Loading agent from config file: {}'.format(config_path))
            agent = agent_class.from_config_file(filename=config_path)
        else:
            print('No config file found; using default constructor.')
            agent = agent_class()

        try:
            agent.setup_logging()
        except AttributeError:
            # If setup_logging is not defined, ignore it.
            pass

        print('Collecting server metadata...')
        agent.collect_server_metadata()
        print('Server metadata collected successfully.')

        print('Converting status to dict...')
        data = agent.status_to_dict()
        print(json.dumps(data, indent=2))

        print('Dumping status to log file...')
        # This will append a timestamped text-dump (status) into agent.log
        agent.status_to_txt()
        print('Status dumped to log file successfully.')

    except Exception as e:
        print('Error: {}'.format(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
