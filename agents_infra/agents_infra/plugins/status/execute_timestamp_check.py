import datetime

import pytz

PLUGIN_NAME = 'timestamp'
PLUGIN_CATEGORY = 'status'


def execute(parent=None, timezone=None, *args, **kwargs):
    utc = pytz.utc.localize(datetime.datetime.utcnow())
    now = utc.astimezone(pytz.timezone(timezone or 'Europe/Kiev'))

    return {'timestamp': now}
