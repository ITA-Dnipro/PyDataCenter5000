import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def main():
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


        data = agent.to_dict()
        print(json.dumps(data, indent=2))

        agent.to_txt()

    except Exception as e:
        print('Error: {0}'.format(str(e)))
        sys.exit(1)

if __name__ == '__main__':
    main()
