# vagrant@DNSserver:~$ python -m agents.dns.start_dns_agent
from agents.dns.dns import DNSAgent

config_path = '/vagrant/agents/dns/config.ini'

# Creating DNS agent
# agent = DNSAgent(server_name='dns')
# agent.setup_logging()
agent = DNSAgent.from_config_file(config_path)

# Collect metadata
agent.collect_server_metadata()

# Prints as a dict
status = agent.status_to_dict()
print(status)

print(agent.critical_processes)
# print(is_process_active('ssh'))
agent._parse_config_file()
