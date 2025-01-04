import paramiko
import json
import os

def create_ssh_key():
    key = paramiko.RSAKey.generate(2048)
    key.write_private_key_file('id_rsa')
    with open('id_rsa.pub', 'w') as f:
        f.write(f"{key.get_name()} {key.get_base64()}")

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

    print("SSH key created, root login enabled, and connection tested with id_rsa.")
