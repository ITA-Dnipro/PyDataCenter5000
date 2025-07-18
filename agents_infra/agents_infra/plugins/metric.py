import os

import psutil

from ..agents.base import ServerAgent
from ..plugins.plugin import plugin


@plugin(ServerAgent, category='metric', built_in=True)
def check_cpu_percent(parent, **kwargs):
    return {'cpu_percent': psutil.cpu_percent(**kwargs)}


@plugin(ServerAgent, category='metric', built_in=True)
def check_ram_percent(parent, **kwargs):
    return {'ram_percent': psutil.virtual_memory()}


@plugin(ServerAgent, category='metric', built_in=True)
def check_disk_usage(parent, **kwargs):
    return {'disk_usage': psutil.disk_usage(os.path.abspath(os.sep))}


@plugin(ServerAgent, category='metric', built_in=True)
def check_load_avg(parent, **kwargs):
    """Get system's average load over the past 1, 5, and 15 minutes."""
    return {'load_avg': os.getloadavg()}
