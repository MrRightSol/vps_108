import paramiko
import json
import os
from datetime import datetime

def create_log_file():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'vps_setup_log_{timestamp}.txt'
    return open(log_filename, 'w')

def log_output(output, logfile):
    logfile.write(output + '\n')

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

    # Read the public key
    with open('id_rsa.pub', 'r') as f:
        public_key = f.read()

    # Add the public key to the server's authorized_keys
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

    # Test command to ensure connection works
    stdin, stdout, stderr = ssh.exec_command('echo "SSH connection successful!"')
    log_output(stdout.read().decode(), logfile)

    ssh.close()

def is_docker_installed(ssh):
    stdin, stdout, stderr = ssh.exec_command('docker --version')
    return stdout.channel.recv_exit_status() == 0

def is_docker_compose_installed(ssh):
    stdin, stdout, stderr = ssh.exec_command('docker-compose --version')
    return stdout.channel.recv_exit_status() == 0

def install_docker_and_compose(server_ip, username, logfile):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=username, pkey=key)

    if not is_docker_installed(ssh):
        commands = [
            'sudo apt-get update',
            'sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common',
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

    log_output(f"User {new_username} created and added to docker group.", logfile)

    # Add the SSH key to the new user's authorized_keys
    with open('id_rsa.pub', 'r') as f:
        public_key = f.read()

    commands = [
        f'mkdir -p /home/{new_username}/.ssh',
        f'bash -c "echo \'{public_key}\' >> /home/{new_username}/.ssh/authorized_keys"',
        f'chown -R {new_username}:{new_username} /home/{new_username}/.ssh',
        f'chmod 700 /home/{new_username}/.ssh',
        f'chmod 600 /home/{new_username}/.ssh/authorized_keys'
    ]

    for command in commands:
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(stdout.read().decode(), logfile)
        log_output(stderr.read().decode(), logfile)

    ssh.close()

def create_folder_structure(ssh, structure, base_path, logfile):
    for key, value in structure.items():
        current_path = f"{base_path}/{key}"  # Correct path construction for Unix-like systems
        stdin, stdout, stderr = ssh.exec_command(f'mkdir -p {current_path}')
        stdout.channel.recv_exit_status()
        log_output(f"Created directory: {current_path}", logfile)

        if 'files' in value:
            for file in value['files']:
                stdin, stdout, stderr = ssh.exec_command(f'touch {current_path}/{file}')
                stdout.channel.recv_exit_status()
                log_output(f"Created file: {current_path}/{file}", logfile)

        if isinstance(value, dict):
            create_folder_structure(ssh, value, current_path, logfile)

def create_caddy_docker_compose(ssh, base_path, logfile):
    caddy_compose = f"""
cat <<EOF > {base_path}/core/caddy/docker-compose.yml
version: '3.9'

services:
  caddy:
    image: caddy:latest
    container_name: caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config

volumes:
  caddy_data:
  caddy_config:
EOF
    """
    caddy_path = f"{base_path}/core/caddy"
    commands = [
        f'mkdir -p {caddy_path}',
        f'{caddy_compose}'
    ]
    log_output(f"Creating Caddy Docker Compose file at: {caddy_path}", logfile)
    for command in commands:
        log_output(f"Executing: {command}", logfile)
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(f"STDOUT: {stdout.read().decode()}", logfile)
        log_output(f"STDERR: {stderr.read().decode()}", logfile)
    log_output("Caddy Docker Compose file created on server.", logfile)

def create_traefik_docker_compose(ssh, base_path, logfile):
    traefik_compose = f"""
cat <<EOF > {base_path}/core/traefik/docker-compose.yml
version: '3.9'

services:
  traefik:
    image: traefik:v2.4
    container_name: traefik
    ports:
      - "80:80"
      - "443:443"
      - "8080:8080" # For Traefik Dashboard
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./traefik.toml:/etc/traefik/traefik.toml
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(``traefik.localhost``)"
      - "traefik.http.routers.api.service=api@internal"
      - "traefik.http.services.api.loadbalancer.server.port=8080"
EOF
    """
    traefik_path = f"{base_path}/core/traefik"
    commands = [
        f'mkdir -p {traefik_path}',
        f'{traefik_compose}'
    ]
    log_output(f"Creating Traefik Docker Compose file at: {traefik_path}", logfile)
    for command in commands:
        log_output(f"Executing: {command}", logfile)
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(f"STDOUT: {stdout.read().decode()}", logfile)
        log_output(f"STDERR: {stderr.read().decode()}", logfile)
    log_output("Traefik Docker Compose file created on server.", logfile)

def create_traefik_config(ssh, base_path, logfile):
    traefik_toml = f"""
cat <<EOF > {base_path}/core/traefik/traefik.toml
[entryPoints]
  [entryPoints.web]
    address = ":80"
  [entryPoints.websecure]
    address = ":443"

[api]
  dashboard = true

[providers]
  [providers.docker]
    endpoint = "unix:///var/run/docker.sock"
    exposedByDefault = false
EOF
    """
    traefik_path = f"{base_path}/core/traefik"
    commands = [
        f'mkdir -p {traefik_path}',
        f'{traefik_toml}'
    ]
    log_output(f"Creating Traefik configuration file at: {traefik_path}", logfile)
    for command in commands:
        log_output(f"Executing: {command}", logfile)
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(f"STDOUT: {stdout.read().decode()}", logfile)
        log_output(f"STDERR: {stderr.read().decode()}", logfile)
    log_output("Traefik configuration file created on server.", logfile)

if __name__ == "__main__":
    # Load credentials from config.json
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)

    server_ip = config['server_ip']
    username = config['username']
    password = config['password']
    new_user = config['new_user']
    new_user_password = config['new_user_password']

    # Load folder structure from folder_struct.json
    with open('folder_struct.json', 'r') as struct_file:
        folder_structure = json.load(struct_file)

    # Create a log file
    logfile = create_log_file()

    # Set up SSH key and root login
    setup_ssh_and_root_login(server_ip, username, password, logfile)

    # Use the SSH key to connect
    ssh = use_ssh_key(server_ip, username, logfile)

    # Install Docker and Docker Compose
    install_docker_and_compose(server_ip, username, logfile)

    # Create a new user and grant Docker access
    create_user(server_ip, username, new_user, new_user_password, logfile)

    # Create the folder structure
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=new_user, pkey=key)

    base_path = f'/home/{new_user}'
    log_output(f"Base path set to: {base_path}", logfile)
    create_folder_structure(ssh, folder_structure['home']['user'], base_path, logfile)

    # Create Docker Compose files for Caddy or Traefik
    # Uncomment the one you want to use
    # create_caddy_docker_compose(ssh, base_path, logfile)
    create_traefik_docker_compose(ssh, base_path, logfile)
    create_traefik_config(ssh, base_path, logfile)  # Needed only for Traefik

    logfile.close()

    print("Setup complete. Logs saved.")
