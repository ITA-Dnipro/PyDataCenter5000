from .agents import base as agent
from .agents.dns.dns import DNSAgent
from .agents.ntp.ntp import NTPAgent
from .agents.smtp.smtp import SMTPAgent
from .agents.web.web import WebAgent
from .plugins.health import check_port
from .plugins.metric import (check_cpu_percent, check_disk_usage,
                             check_load_avg, check_ram_percent)
from .plugins.plugin import plugin, register_plugin, unregister_plugin
from .plugins.status import check_os, check_timestamp, check_uptime
from .utils import configtools

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
