from . import agent
from .dns.dns import DNSAgent
from .ntp.ntp import NTPAgent
from .smtp.smtp import SMTPAgent
from .utils import configtools
from .web.web import WebAgent

# Make sure all global configurations (from agents/config.ini) are
# parsed before any concrete child is instantiated.
cfg = configtools.load_global_config()

if cfg:
    agent.ServerAgent.controller_url = configtools.get_config_option(
        cfg, 'controller', 'url'
    )
    agent.ServerAgent.api_prefix = configtools.get_config_option(
        cfg,
        'controller',
        'api_prefix',
        default=agent.ServerAgent.api_prefix,
    )

    agent.ServerAgent.auth_token_type = configtools.get_config_option(
        cfg,
        'controller',
        'auth_token_type',
        default=agent.ServerAgent.auth_token_type,
    )

    agent.ServerAgent.whitelist_commands = configtools.get_config_option(
        cfg,
        'controller',
        'whitelist_commands',
        cast=configtools.parse_csv_list,
    )

    agent.ServerAgent.critical_processes = configtools.get_config_option(
        cfg,
        'servers',
        'critical_processes',
        cast=configtools.parse_csv_list,
    )
