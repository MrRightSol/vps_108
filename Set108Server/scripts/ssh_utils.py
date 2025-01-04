import paramiko
import os
from scripts.logging_utils import log_output

def create_ssh_key(logfile):
    if not os.path.exists('id_rsa') or not os.path.exists('id_rsa.pub'):
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file('id_rsa')
        with open('id_rsa.pub', 'w') as f:
            f.write(f"{key.get_name()} {key.get_base64()}")
        log_output("SSH key pair created.", logfile)
    else:
        log_output("SSH key pair already exists.", logfile)

def setup_ssh_and_root_login(server_ip, username, password, logfile):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(server_ip, username=username, password=password)

    create_ssh_key(logfile)

    with open('id_rsa.pub', 'r') as f:
        public_key = f.read()

    commands = [
        'mkdir -p ~/.ssh',
        f'echo "{public_key}" >> ~/.ssh/authorized_keys',
        'chmod 600 ~/.ssh/authorized_keys',
        'chmod 700 ~/.ssh',
        'sudo sed -i "s/PermitRootLogin prohibit-password/PermitRootLogin yes/" /etc/ssh/sshd_config',
        'sudo systemctl restart sshd'
    ]

    for command in commands:
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(stdout.read().decode(), logfile)
        log_output(stderr.read().decode(), logfile)

    ssh.close()

def use_ssh_key(server_ip, username, logfile):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=username, pkey=key)

    stdin, stdout, stderr = ssh.exec_command('echo "SSH connection successful!"')
    stdout.channel.recv_exit_status()
    log_output(stdout.read().decode(), logfile)
    log_output(stderr.read().decode(), logfile)

    ssh.close()
