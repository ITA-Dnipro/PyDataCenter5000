# Make sure all global configurations (from global.ini) are
# parsed before any concrete child is instantiated.

from .agents import base as agent
from .agents.dns.dns import DNSAgent
from .agents.ntp.ntp import NTPAgent
from .agents.smtp.smtp import SMTPAgent
from .agents.web.web import WebAgent
from .utils import configtools, timestamp

cfg = configtools.load_global_config()

if cfg is not None:
    # Prepare config as a dictionary
    config = {
        'urls': configtools.get_config_option(
            cfg, 'controller', 'urls', cast=configtools.parse_csv_list
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
        'post_agent_log_url': configtools.get_config_option(
            cfg,
            'logging',
            'post_agent_log_url',
            default='/logs/',
        ),
        'send_logs_to_controller': configtools.get_config_option(
            cfg,
            'logging',
            'send_logs_to_controller',
            cast=lambda v: str(v).lower() in ('true', '1', 'yes'),
            default=False,
        ),
        'name': 'global',  # Needed for validator
        'port': 0,
        'interface': None,
    }

    # Assign global config
    agent.ServerAgent.config = agent.Config.from_dict(config)
