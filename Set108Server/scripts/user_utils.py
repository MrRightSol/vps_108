import paramiko
from scripts.logging_utils import log_output

def create_user(server_ip, root_username, new_username, new_password, logfile):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=root_username, pkey=key)

    commands = [
        f'sudo adduser --disabled-password --gecos "" {new_username}',
        f'echo "{new_username}:{new_password}" | sudo chpasswd',
        f'sudo usermod -aG sudo {new_username}',
        f'sudo usermod -aG docker {new_username}'
    ]

    for command in commands:
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(stdout.read().decode(), logfile)
        log_output(stderr.read().decode(), logfile)

    ssh.close()
