import paramiko
from scripts.logging_utils import log_output

def is_docker_installed(ssh):
    stdin, stdout, stderr = ssh.exec_command("docker --version")
    stdout.channel.recv_exit_status()
    return 'Docker version' in stdout.read().decode()

def is_docker_compose_installed(ssh):
    stdin, stdout, stderr = ssh.exec_command("docker-compose --version")
    stdout.channel.recv_exit_status()
    return 'docker-compose version' in stdout.read().decode()

def create_docker_network(ssh, network_name, logfile):
    log_output(f"Creating Docker network: {network_name}", logfile)
    command = f'docker network create {network_name}'
    stdin, stdout, stderr = ssh.exec_command(command)
    stdout.channel.recv_exit_status()
    log_output(stdout.read().decode(), logfile)
    log_output(stderr.read().decode(), logfile)

def install_docker_and_compose(server_ip, username, logfile):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=username, pkey=key)

    if not is_docker_installed(ssh):
        commands = [
            'sudo apt-get update',
            'sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release',
            'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg',
            'echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null',
            'sudo apt-get update',
            'sudo apt-get install -y docker-ce',
            'sudo systemctl status docker'
        ]

        for command in commands:
            stdin, stdout, stderr = ssh.exec_command(command)
            stdout.channel.recv_exit_status()
            log_output(stdout.read().decode(), logfile)
            log_output(stderr.read().decode(), logfile)

        log_output("Docker installed successfully.", logfile)
    else:
        log_output("Docker is already installed.", logfile)

    if not is_docker_compose_installed(ssh):
        commands = [
            'sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
            'sudo chmod +x /usr/local/bin/docker-compose',
            'docker-compose --version'
        ]

        for command in commands:
            stdin, stdout, stderr = ssh.exec_command(command)
            stdout.channel.recv_exit_status()
            log_output(stdout.read().decode(), logfile)
            log_output(stderr.read().decode(), logfile)

        log_output("Docker Compose installed successfully.", logfile)
    else:
        log_output("Docker Compose is already installed.", logfile)

    ssh.close()
