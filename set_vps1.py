import paramiko
import json
import os

def create_ssh_key():
    if not os.path.exists('id_rsa') or not os.path.exists('id_rsa.pub'):
        key = paramiko.RSAKey.generate(2048)
        key.write_private_key_file('id_rsa')
        with open('id_rsa.pub', 'w') as f:
            f.write(f"{key.get_name()} {key.get_base64()}")
        print("SSH key pair created.")
    else:
        print("SSH key pair already exists.")

def setup_ssh_and_root_login(server_ip, username, password):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(server_ip, username=username, password=password)

    create_ssh_key()

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

    ssh.close()

def use_ssh_key(server_ip, username):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=username, pkey=key)

    # Test command to ensure connection works
    stdin, stdout, stderr = ssh.exec_command('echo "SSH connection successful!"')
    print(stdout.read().decode())

    ssh.close()

def install_docker_and_compose(server_ip, username):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=username, pkey=key)

    commands = [
        'sudo apt-get update',
        'sudo apt-get install -y apt-transport-https ca-certificates curl software-properties-common',
        'curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -',
        'sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"',
        'sudo apt-get update',
        'sudo apt-get install -y docker-ce',
        'sudo systemctl status docker',
        'sudo curl -L "https://github.com/docker/compose/releases/download/1.29.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose',
        'sudo chmod +x /usr/local/bin/docker-compose',
        'docker-compose --version'
    ]

    for command in commands:
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        print(stdout.read().decode())
        print(stderr.read().decode())

    ssh.close()

if __name__ == "__main__":
    # Load credentials from config.json
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)

    server_ip = config['server_ip']
    username = config['username']
    password = config['password']

    # Set up SSH key and root login
    setup_ssh_and_root_login(server_ip, username, password)

    # Use the SSH key to connect
    use_ssh_key(server_ip, username)

    # Install Docker and Docker Compose
    install_docker_and_compose(server_ip, username)

    print("SSH key created or verified, root login enabled, and Docker with Docker Compose installed.")
