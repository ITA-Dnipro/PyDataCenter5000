import os
import socket
import subprocess

from ..exceptions import BadProcessReturnCode


def get_env_or_param(param_value, env_name):
    """
    Get value from parameter or environment variable.

    Args:
        param_value: Value passed as parameter
        env_name (str): Name of environment variable

    Returns:
        The parameter value if provided, otherwise environment variable

    Raises:
        ValueError: If neither parameter nor environment variable is set
    """
    if param_value is None and env_name not in os.environ:
        raise ValueError('%s environment variable is not set.' % env_name)
    return param_value or os.environ[env_name]


def is_valid_ip(output):
    try:
        output = output.strip()
        parts = output.split('.')
        if len(parts) != 4:
            return False
        if not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            return False
        socket.inet_aton(output)
        return True
    except Exception:
        return False


def execute_shell_command(
    cmd, shell=False, input=None, encoding='utf-8', **kwargs
):
    """
    Execute Linux shell command.

    Parameters:
        cmd (Any): Shell command to execute.
        shell (bool, optional): Whether to execute command through shell.
            Default is False.
        input (str, optional): Data to send to command's standard input
            (stdin).
        encoding (str, optional): If specified, decode the output using
            this encoding.

    Returns:
        tuple: stdout, stderr

    Raises:
        BadProcessReturnCode: If shell command fails with return code
            different from 0.
    """
    # Always capture command output with PIPE.
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=shell,
        **kwargs
    )

    stdout, stderr = proc.communicate(input=input)

    if encoding:
        stdout, stderr = stdout.decode(encoding), stderr.decode(encoding)

    if proc.returncode != 0:
        raise BadProcessReturnCode(
            'Shell command failed with return code %d and stderr %s' % (
                proc.returncode, stderr
            )
        )

    return stdout.strip()
