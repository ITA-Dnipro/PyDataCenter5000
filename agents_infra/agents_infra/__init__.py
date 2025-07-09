# Make sure all global configurations (from global.ini) are
# parsed before any concrete child is instantiated.

from .agents import base as agent
from .agents.dns.dns import DNSAgent
from .agents.ntp.ntp import NTPAgent
from .agents.smtp.smtp import SMTPAgent
from .agents.web.web import WebAgent
from .utils import configtools

cfg = configtools.load_global_config()

if cfg:
    # Saving global config
    agent.ServerAgent.config = {
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
    }
