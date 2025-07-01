# vagrant@DNSserver:~$ python -m agents.dns.start_dns_agent
from agents.dns.dns import DNSAgent

config_path = '/vagrant/agents/dns/config.ini'

# agent = DNSAgent.from_config_file(config_path)

config_dict = {
    'name': 'dns',
    'api_prefix': 'api/v1/',
    'url': 'http://10.0.2.2:8000/',
    'critical_processes': ['named', 'ssh', 'sshd'],
    'whitelist_commands': ['uptime', 'df -h', 'ls', 'whoami', 'test'],
    'port': 53,
    'auth_token_type': None,
    'interface': 'enp0s3',
}

agent = DNSAgent(config=config_dict)

# Collect metadata
agent.collect_server_metadata()

# Prints as a dict
status = agent.status_to_dict()
print(status)

# print(agent.config.get('critical_processes'))
print(agent.config.get('whitelist_commands'))
# print(agent.config)

# print(agent.config.get('url'))
# print(is_process_active('ssh'))
# agent._parse_config_file()
