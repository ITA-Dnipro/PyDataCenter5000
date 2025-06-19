import logging
import os
import tempfile

import pytest


@pytest.yield_fixture(scope='session')
def setup_temp_file_logging():
    config_file = tempfile.NamedTemporaryFile('w', delete=False)
    log_file = tempfile.NamedTemporaryFile('w', delete=False)

    config_file.write("""
[loggers]
keys=root,fallback,supervisor

[handlers]
keys=fallback,file

[formatters]
keys=minimal

[logger_root]
level=NOTSET
handlers=

[logger_fallback]
level=ERROR
handlers=fallback
qualname=fallback
propagate=0

[logger_supervisor]
level=INFO
handlers=file
qualname=mock-server-supervisor
propagate=0

[handler_fallback]
class=StreamHandler
formatter=minimal
args=(sys.stdout,)

[handler_file]
class=FileHandler
formatter=minimal
args=('%(filename)s', 'w')

[formatter_minimal]
format=%(levelname)s : %(message)s
style=%
class=logging.Formatter
    """)

    config_file.close()
    log_file.close()

    logging.config.fileConfig(
        config_file.name, defaults={'filename': log_file.name}
    )

    yield

    os.remove(config_file.name)
    os.remove(log_file.name)
