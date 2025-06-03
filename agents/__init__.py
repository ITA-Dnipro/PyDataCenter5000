import ConfigParser
import pkg_resources

from . import agent
from .utils import helpers

# Make sure all global configurations (from agents/config.ini) are
# parsed before any concrete child is instantiated.
global_config = ConfigParser.ConfigParser()
global_config.read(pkg_resources.resource_filename(__name__, 'global.ini'))

if global_config.sections():
    agent.ServerAgent.controller_url = helpers.get_config_option(
        global_config, 'controller', 'url'
    )
    agent.ServerAgent.api_prefix = helpers.get_config_option(
        global_config, 'controller', 'api_prefix', 'api/'
    )
    agent.ServerAgent.whitelist_commands = helpers.get_config_option(
        global_config,
        'controller',
        'whitelist_commands',
        cast=helpers.parse_csv_list,
    )
