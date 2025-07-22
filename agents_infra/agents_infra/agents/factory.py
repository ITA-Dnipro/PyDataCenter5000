import os

from agents_infra.agents.dns.dns import DNSAgent
from agents_infra.agents.ntp.ntp import NTPAgent
from agents_infra.agents.smtp.smtp import SMTPAgent
from agents_infra.agents.web.web import WebAgent
from agents_infra.utils.configtools import Config
from agents_infra.utils.logtools import maybe_log_message

AGENT_CLASS_MAP = {
    'dns': DNSAgent,
    'ntp': NTPAgent,
    'smtp': SMTPAgent,
    'web': WebAgent,
}


def agent_factory(agent_name):
    agent_class = AGENT_CLASS_MAP[agent_name]
    config_path = os.path.join(
        os.path.dirname(__file__), agent_name, 'config.ini'
    )
    if os.path.exists(config_path):
        agent = agent_class.from_config_file(filename=config_path)
    else:
        maybe_log_message(
            "WARNING: No config file found for agent '%s' at '%s'. "
            'Falling back to default minimal config.'
            'This is NOT recommended for production.'
            % (agent_name, config_path),
            level='warning'
        )
        config = Config(name=agent_name)
        agent = agent_class(config=config)
    agent.setup_logging()
    agent.collect_server_metadata()
    return agent
