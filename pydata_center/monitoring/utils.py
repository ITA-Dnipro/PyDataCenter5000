import socket

import paramiko


def ping_vm_tcp(ip, port=22, timeout=3):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def run_remote_health_check(vm_ip, username, password=None):
    try:
        if not ping_vm_tcp(vm_ip):
            print('VM not reachable via TCP/SSH')
            return False

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(vm_ip, username=username, password=password)

        stdin, stdout, stderr = ssh.exec_command(
            'cd ~/PyDataCenter5000 && ~/python2.6/bin/python -m agents.smtp.check_smtp_health'
        )
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        ssh.close()
        print(output)
        if error:
            print('SSH Error:', error)
        return output
    except Exception as e:
        print('SSH Exception:', e)
        return False
