import time

import psutil

PLUGIN_NAME = 'uptime'
PLUGIN_CATEGORY = 'status'


def execute(parent=None, *args, **kwargs):
    uptime = time.time() - psutil.boot_time()
    return {'uptime': uptime}
