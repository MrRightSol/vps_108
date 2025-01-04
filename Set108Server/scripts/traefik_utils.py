import os
import tempfile
import paramiko
from scripts.logging_utils import log_output

def create_traefik_docker_compose(ssh, base_path, logfile):
    traefik_compose_content = '''version: "3.8"

services:
  traefik:
    image: "traefik:latest"
    container_name: traefik
    restart: unless-stopped
    security_opt:
      - "no-new-privileges:true"
    networks:
      - proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/etc/localtime:/etc/localtime:ro"
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./traefik-data/traefik.yml:/traefik.yml:ro"
      - "./traefik-data/acme.json:/acme.json"
      - "./traefik-data/configurations:/configurations"
    labels:
      - traefik.enable=true
      - traefik.docker.network=proxy
      - traefik.http.routers.traefik-secure.entrypoints=websecure
      - traefik.http.routers.traefik-secure.rule=Host(`traefik.scraperator.com`)
      - traefik.http.routers.traefik-secure.service=api@internal
      - traefik.http.routers.traefik-secure.middlewares=user-auth@file

  portainer:
    image: "portainer/portainer-ce:latest"
    container_name: portainer
    restart: unless-stopped
    security_opt:
      - "no-new-privileges:true"
    networks:
      - proxy
    volumes:
      - "/etc/localtime:/etc/localtime:ro"
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./portainer-data:/data"
    labels:
      - traefik.enable=true
      - traefik.docker.network=proxy
      - traefik.http.routers.portainer-secure.entrypoints=websecure
      - traefik.http.routers.portainer-secure.rule=Host(`port.scraperator.com`)
      - traefik.http.routers.portainer-secure.service=portainer
      - traefik.http.services.portainer.loadbalancer.server.port=9000

networks:
  proxy:
    external: true
'''

    # Write the docker-compose content to a temporary file
    with tempfile.NamedTemporaryFile(delete=False) as tmpfile:
        tmpfile.write(traefik_compose_content.encode('utf-8'))
        tmpfile_path = tmpfile.name

    traefik_path = f"{base_path}/core/traefik"
    remote_file_path = f"{traefik_path}/docker-compose.yml"

    # Create directories on the server
    commands = [
        f'mkdir -p {traefik_path}/traefik-data/configurations'
    ]
    for command in commands:
        log_output(f"Executing: {command}", logfile)
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(stdout.read().decode(), logfile)
        log_output(stderr.read().decode(), logfile)

    # Upload the temporary file to the server
    sftp = ssh.open_sftp()
    sftp.put(tmpfile_path, remote_file_path)
    sftp.close()

    log_output(f"Traefik Docker Compose file created at: {remote_file_path}", logfile)

    # Remove the temporary file
    os.remove(tmpfile_path)



def create_traefik_config(ssh, base_path, logfile):
    traefik_yml_content = '''
api:
  dashboard: true

entryPoints:
  web:
    address: ":80"
    http:
      redirections:
        entryPoint:
          to: websecure

  websecure:
    address: ":443"
    http:
      middlewares:
        - secureHeaders@file
      tls:
        certResolver: letsencrypt

providers:
  docker:
    endpoint: "unix:///var/run/docker.sock"
    exposedByDefault: false
  file:
    filename: /configurations/dynamic.yml

certificatesResolvers:
  letsencrypt:
    acme:
      email: markoos@scraperator.com
      storage: acme.json
      keyType: EC384
      httpChallenge:
        entryPoint: web
'''

    dynamic_yml_content = '''
# Dynamic configuration
http:
  middlewares:
    secureHeaders:
      headers:
        sslRedirect: true
        forceSTSHeader: true
        stsIncludeSubdomains: true
        stsPreload: true
        stsSeconds: 31536000
    user-auth:
      basicAuth:
        users:
          - "marktraf:$apr1$2EjH7K7r$z4rpxjxPKqFT5fwBo3xT/0"

tls:
  options:
    default:
      cipherSuites:
        - TLS_ECDHE_ECDSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384
        - TLS_ECDHE_ECDSA_WITH_AES_128_GCM_SHA256
        - TLS_ECDHE_RSA_WITH_AES_128_GCM_SHA256
        - TLS_ECDHE_ECDSA_WITH_CHACHA20_POLY1305
        - TLS_ECDHE_RSA_WITH_CHACHA20_POLY1305
      minVersion: VersionTLS12
'''

    acme_json_content = '{}'

    # Write the content to local temporary files
    with tempfile.NamedTemporaryFile(delete=False) as tmp_traefik_yml, \
         tempfile.NamedTemporaryFile(delete=False) as tmp_dynamic_yml, \
         tempfile.NamedTemporaryFile(delete=False) as tmp_acme_json:
        
        tmp_traefik_yml.write(traefik_yml_content.encode('utf-8'))
        tmp_dynamic_yml.write(dynamic_yml_content.encode('utf-8'))
        tmp_acme_json.write(acme_json_content.encode('utf-8'))
        
        tmp_traefik_yml_path = tmp_traefik_yml.name
        tmp_dynamic_yml_path = tmp_dynamic_yml.name
        tmp_acme_json_path = tmp_acme_json.name

    traefik_path = f"{base_path}/core/traefik/traefik-data"
    remote_traefik_yml_path = f"{traefik_path}/traefik.yml"
    remote_dynamic_yml_path = f"{traefik_path}/configurations/dynamic.yml"
    remote_acme_json_path = f"{traefik_path}/acme.json"

    # Create directories on the server
    commands = [
        f'mkdir -p {traefik_path}/configurations'
    ]
    for command in commands:
        log_output(f"Executing: {command}", logfile)
        stdin, stdout, stderr = ssh.exec_command(command)
        stdout.channel.recv_exit_status()
        log_output(stdout.read().decode(), logfile)
        log_output(stderr.read().decode(), logfile)

    # Upload the temporary files to the server
    sftp = ssh.open_sftp()
    sftp.put(tmp_traefik_yml_path, remote_traefik_yml_path)
    sftp.put(tmp_dynamic_yml_path, remote_dynamic_yml_path)
    sftp.put(tmp_acme_json_path, remote_acme_json_path)
    sftp.chmod(remote_acme_json_path, 0o600)
    sftp.close()

    log_output(f"Traefik configuration files created at: {traefik_path}", logfile)

    # Remove the temporary files
    os.remove(tmp_traefik_yml_path)
    os.remove(tmp_dynamic_yml_path)
    os.remove(tmp_acme_json_path)