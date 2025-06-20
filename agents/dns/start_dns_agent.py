# vagrant@DNSserver:~$ python -m agents.dns.start_dns_agent
from agents.dns.dns import DNSAgent

config_path = '/vagrant/agents/dns/config.ini'

# Creating DNS agent
agent = DNSAgent.from_config_file(filename=config_path)
# agent = DNSAgent()
# print(agent.server_name)

# Collect metadata
agent.collect_server_metadata()

# Prints as a dict
status = agent.status_to_dict()
print(status)

# Save to logs
agent.status_to_txt()
