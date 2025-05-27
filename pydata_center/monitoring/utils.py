import logging
import socket

import paramiko

from .exceptions import SSHConnectionFailed, VMNotReachable

log = logging.getLogger(__name__)


def ping_vm_tcp(ip, port=22, timeout=3):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def run_remote_health_check(vm_ip, username, password=None):
    try:
        if not ping_vm_tcp(vm_ip):
            raise VMNotReachable(vm_ip)

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            ssh.connect(vm_ip, username=username, password=password)
        except paramiko.SSHException as ssh_err:
            log.error('SSH connection failed for %s: %s', vm_ip, ssh_err)
            raise SSHConnectionFailed(vm_ip, str(ssh_err))

        try:
            stdin, stdout, stderr = ssh.exec_command(
                'cd ~/PyDataCenter5000 && '
                '~/python2.6/bin/python -m agents.smtp.check_smtp_health'
            )
            output = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            if error:
                log.warning('SSH command error on %s: %s', vm_ip, error)
            return output
        finally:
            ssh.close()

    except (VMNotReachable, SSHConnectionFailed) as custom_exc:
        # Let DRF handle this via the custom_exception_handler
        raise custom_exc

    except Exception as e:
        log.exception('Unhandled error in check_smtp_health')
        raise SSHConnectionFailed(vm_ip, str(e))
