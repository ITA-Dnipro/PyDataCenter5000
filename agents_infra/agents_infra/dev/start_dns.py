# vagrant@DNSserver:~$ python -m agents_infra.dev.start_dns
from agents_infra.agents.dns.dns import DNSAgentNamed

config_path = '/vagrant/agents_infra/agents_infra/agents/dns/config.ini'

# config_dict = {
#     'name': 'dns_named',
#     'api_prefix': 'api/v1/',
#     'url': 'http://localhost:8000/',
#     'critical_processes': ['named'],
#     'whitelist_commands': ['dig', 'whoami', 'ls'],
#     'port': 53,
#     'auth_token_type': None,
#     'interface': 'enp0s3',
# }
# Creating DNS agent
agent = DNSAgentNamed.from_config_file(filename=config_path)

# Collect metadata
agent.collect_server_metadata()
agent._are_all_critical_processes_active(restart=True)

# Prints as a dict
status = agent.status_to_dict()
print(status)
print(agent.protocol)
