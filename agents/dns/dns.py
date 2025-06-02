from ..agent import ServerAgent
import json

class DNSAgent(ServerAgent):

    def __init__(
        self,
        server_name='dns',
        port=53,
        processes=None,
        interface=None,
        controller_url=None,
    ):
        super(DNSAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['named', 'bind9'],
            interface=interface,
            controller_url=controller_url,
        )

if __name__ == '__main__':
    try:
        agent = DNSAgent()

        agent.collect_server_metadata()

        data = agent.status_to_dict()
        print(json.dumps(data, indent=2))

        agent.controller_url = 'http://192.168.64.1:8000/api/v1/server/status/'

        if agent.controller_url:
            post_result = agent.post_data(agent.controller_url, data)
            print('Post result:', post_result)
            print('Status to controller: ', agent.status_to_controller())
        else:
            print('No controller URL specified, skipping POST request.')

    except Exception as e:
        print('Error: {0}'.format(str(e)))

