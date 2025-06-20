# vagrant@DNSserver:~$ python -m agents.dns.start_dns_agent
from agents.dns.dns import DNSAgent
from agents.utils.helpers import is_process_active

config_path = '/vagrant/agents/dns/config.ini'

# Creating DNS agent
agent = DNSAgent(server_name='my_server')
agent.setup_logging()
agent = DNSAgent.from_config_file('/path/to/your/config/file')

# Collect metadata
agent.collect_server_metadata()

# Prints as a dict
status = agent.status_to_dict()
print(status)

# Save to logs
agent.status_to_txt()

print(agent.critical_processes)
print(is_process_active(agent.logger, agent.fallback_logger, 'ssh'))
