# vagrant@DNSserver:~$ python -m agents_infra.dev.start_dns
from agents_infra.agents.dns.dns import DNSAgentNamed

config_path = '/vagrant/agents_infra/agents_infra/agents/dns/config.ini'

# Creating DNS agent
agent = DNSAgentNamed.from_config_file(filename=config_path)

# Collect metadata
agent.collect_server_metadata()

# Prints as a dict
status = agent.status_to_dict()
print(status)
print(agent.config)
