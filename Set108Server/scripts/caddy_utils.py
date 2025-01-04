import os
import paramiko
from scripts.logging_utils import log_output

def create_caddy_docker_compose(ssh, base_path, logfile):
    caddy_compose = f"""
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