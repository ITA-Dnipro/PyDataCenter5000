import json
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
)


def main():
    """Developer utility to get agent status information.

    This script retrieves and displays the status of a specified agent.
    It outputs the agent's data in JSON format to stdout and writes logs
    to a text file using the agent's to_txt() method.

    Usage:
        python get_agent_status.py <agent_name>

    Args:
        None (uses sys.argv[1] for agent_name)

    Returns:
        None (prints JSON to stdout and writes logs to text file)
    """
    if len(sys.argv) != 2:
        print('Usage: python run_agent.py <agent_name>')
        sys.exit(1)

    agent_name = sys.argv[1]

    try:
        module = __import__('agents.{0}.{0}'.format(agent_name), fromlist=[''])

        if agent_name == 'web':
            agent_class = getattr(module, 'WebAgent')
        else:
            agent_class = getattr(module, agent_name.upper() + 'Agent')
        agent = agent_class()

        agent.collect_server_metadata()

        data = agent.status_to_dict()
        print(json.dumps(data, indent=2))

    except Exception as e:
        print('Error: {0}'.format(str(e)))
        sys.exit(1)


if __name__ == '__main__':
    main()
