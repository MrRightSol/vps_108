import paramiko
from scripts.logging_utils import log_output

def create_docker_network(server_ip, username, logfile):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=username, pkey=key)

    command = "docker network create my_network"
    stdin, stdout, stderr = ssh.exec_command(command)
    stdout.channel.recv_exit_status()
    log_output(stdout.read().decode(), logfile)
    log_output(stderr.read().decode(), logfile)

    ssh.close()
