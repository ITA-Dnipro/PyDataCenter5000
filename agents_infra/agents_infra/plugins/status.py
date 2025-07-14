import datetime
import platform
import time

import psutil
import pytz

from ..agents.base import ServerAgent
from ..plugins.plugin import plugin


@plugin(ServerAgent, category='status', built_in=True)
def check_os(parent, *args, **kwargs):
    return {'os': platform.system().lower() or 'unknown'}


@plugin(ServerAgent, category='status', built_in=True)
def check_timestamp(parent, timezone=None, *args, **kwargs):
    utc = pytz.utc.localize(datetime.datetime.utcnow())
    now = utc.astimezone(pytz.timezone(timezone or 'Europe/Kiev'))

    return {'timestamp': now}


@plugin(ServerAgent, category='status', built_in=True)
def check_uptime(parent, *args, **kwargs):
    uptime = time.time() - psutil.boot_time()
    return {'uptime': uptime}
