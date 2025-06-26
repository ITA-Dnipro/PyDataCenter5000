import time

from .agents import base as agent
from .agents.dns.dns import DNSAgent
from .agents.ntp.ntp import NTPAgent
from .agents.smtp.smtp import SMTPAgent
from .agents.web.web import WebAgent
from .utils import configtools

cfg = configtools.load_global_config()

if cfg:
    urls = configtools.get_config_option(cfg, 'controller', 'urls')

    if isinstance(urls, str):
        controller_urls = [
            url.strip() for url in urls.split(',') if url.strip()
        ]
    else:
        controller_urls = []

    agent.ServerAgent.controller_urls = controller_urls

    # Default current controller is the first one
    if controller_urls:
        agent.ServerAgent.current_controller = controller_urls[0]
        agent.ServerAgent.last_success_time = time.time()

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