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
            print("VM not reachable via TCP/SSH")
            return False

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        ssh.connect(vm_ip, username=username, password=password)

        stdin, stdout, stderr = ssh.exec_command(
            '~/python2.6/bin/python ~/PyDataCenter5000/agents/check_smtp_health.py'
        )
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        ssh.close()
        print(1)
        print("Output:", output)
        print(2)
        print(3)
        if error:
            print("SSH Error:", error)
        print("Output2", output)
        return output
    except Exception as e:
        print("SSH Exception:", e)
        return False
