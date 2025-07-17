# Make sure all global configurations (from global.ini) are
# parsed before any concrete child is instantiated.

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

cfg = configtools.load_global_config()

if cfg:
    # Prepare config as a dictionary
    config = {
        'url': configtools.get_config_option(
            cfg, 'controller', 'url', default=''
        ),
        'api_prefix': configtools.get_config_option(
            cfg, 'controller', 'api_prefix', default='api/'
        ),
        'auth_token_type': configtools.get_config_option(
            cfg, 'controller', 'auth_token_type'
        ),
        'whitelist_commands': configtools.get_config_option(
            cfg,
            'controller',
            'whitelist_commands',
            cast=configtools.parse_csv_list
        ),
        'critical_processes': configtools.get_config_option(
            cfg,
            'servers',
            'critical_processes',
            cast=configtools.parse_csv_list
        ),
        'name': 'global',  # Needed for validator
        'port': 0,
        'interface': None,
    }

    # Assign global config
    agent.ServerAgent.config = agent.Config.from_dict(config)
