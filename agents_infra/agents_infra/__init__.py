# Make sure all global configurations (from global.ini) are
# parsed before any concrete child is instantiated.
import logging

from .agents import base as agent
from .agents.dns.dns import DNSAgent
from .agents.ntp.ntp import NTPAgent
from .agents.smtp.smtp import SMTPAgent
from .agents.web.web import WebAgent
from .utils import Authentication, AuthStrategyFactory, configtools, timestamp

logging.basicConfig(
    level=logging.INFO, format='%(levelname)s : %(name)s : %(message)s'
)
cfg = configtools.load_global_config()

if cfg is not None:
    # Prepare config as a dictionary
    config = {
        'urls': configtools.get_config_option(
            cfg, 'controller', 'urls',
            cast=configtools.parse_csv_list
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
    if config['auth_token_type']:
        factory = AuthStrategyFactory()
        Authentication.set_strategy(
            factory.from_str(config['auth_token_type'])
            )
    else:
        logging.getLogger(__name__).warning(
            'No auth_token_type provided in global.ini, '
            'authentication will not be used.'
        )
