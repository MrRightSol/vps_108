import json
import paramiko
from scripts.logging_utils import create_log_file, log_output
from scripts.ssh_utils import setup_ssh_and_root_login, use_ssh_key
from scripts.docker_utils import install_docker_and_compose
from scripts.user_utils import create_user
from scripts.docker_network_utils import create_docker_network
from scripts.folder_structure_utils import create_folder_structure
from scripts.traefik_utils import create_traefik_docker_compose, create_traefik_config
from scripts.caddy_utils import create_caddy_docker_compose
from scripts.elastic_stack_utils import (
    create_elk_docker_compose, create_env_file, 
    create_logstash_config, create_filebeat_config,
    create_kibana_config, create_metricbeat_config)

def load_config(file_path):
    with open(file_path, 'r') as file:
        return json.load(file)

if __name__ == "__main__":
    config = load_config('config.json')

    server_ip = config["server_ip"]
    username = config["username"]
    password = config["password"]
    new_username = config["new_user"]
    new_password = config["new_user_password"]

    logfile = create_log_file()

    setup_ssh_and_root_login(server_ip, username, password, logfile)
    use_ssh_key(server_ip, username, logfile)
    
    install_docker_and_compose(server_ip, username, logfile)
    
    create_user(server_ip, username, new_username, new_password, logfile)

    create_docker_network(server_ip, username, logfile)

    with open('folder_struct.json', 'r') as file:
        folder_structure = json.load(file)
    
    base_path = f'/home/{new_username}'

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    key = paramiko.RSAKey(filename='id_rsa')
    ssh.connect(server_ip, username=new_username, pkey=key)

    create_folder_structure(ssh, folder_structure['home']['user'], base_path, logfile)

    #create_caddy_docker_compose(ssh, base_path, logfile)

    create_traefik_docker_compose(ssh, base_path, logfile)
    create_traefik_config(ssh, base_path, logfile)

    create_elk_docker_compose(ssh, base_path, logfile)
    create_env_file(ssh, base_path, logfile)
    create_logstash_config(ssh, base_path, logfile)
    create_filebeat_config(ssh, base_path, logfile)
    create_kibana_config(ssh, base_path, logfile)
    create_metricbeat_config(ssh, base_path, logfile)

    ssh.close()