from .agents import base as agent
from .agents.dns.dns import DNSAgent
from .agents.ntp.ntp import NTPAgent
from .agents.smtp.smtp import SMTPAgent
from .agents.web.web import WebAgent
from .plugins.health import execute_port_check
from .plugins.metric import (execute_cpu_check, execute_disk_check,
                             execute_load_avg_check, execute_ram_check)
from .plugins.plugin import register_plugin, unregister_plugin
from .plugins.status import execute_timestamp_check, execute_uptime_check
from .utils import configtools

# Register default plugins.
register_plugin(execute_cpu_check, agent.ServerAgent, built_in=True)
register_plugin(execute_ram_check, agent.ServerAgent, built_in=True)
register_plugin(execute_load_avg_check, agent.ServerAgent, built_in=True)
register_plugin(execute_disk_check, agent.ServerAgent, built_in=True)
register_plugin(execute_port_check, agent.ServerAgent, built_in=True)
register_plugin(execute_timestamp_check, agent.ServerAgent, built_in=True)
register_plugin(execute_uptime_check, agent.ServerAgent, built_in=True)

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
