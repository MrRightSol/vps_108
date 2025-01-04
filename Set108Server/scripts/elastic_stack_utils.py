import os
import tempfile
from scripts.logging_utils import log_output

def create_elk_docker_compose(ssh, base_path, logfile):
    docker_compose_content = '''version: "3.8"
volumes:
  certs:
    driver: local
  esdata01:
    driver: local
  kibanadata:
    driver: local
  metricbeatdata01:
    driver: local
  filebeatdata01:
    driver: local
  logstashdata01:
    driver: local
  fleetserverdata:
    driver: local

networks:
  default:
    name: elastic
    external: false

services:
  setup:
    image: docker.elastic.co/elasticsearch/elasticsearch:\${ STACK_VERSION}
    volumes:
      - certs:/usr/share/elasticsearch/config/certs
    user: "0"
    command: >
      bash -c '
        if [ x\${ELASTIC_PASSWORD} == x ]; then
          echo "Set the ELASTIC_PASSWORD environment variable in the .env file";
          exit 1;
        elif [ x\${KIBANA_PASSWORD} == x ]; then
          echo "Set the KIBANA_PASSWORD environment variable in the .env file";
          exit 1;
        fi;
        if [ ! -f config/certs/ca.zip ]; then
          echo "Creating CA";
          bin/elasticsearch-certutil ca --silent --pem -out config/certs/ca.zip;
          unzip config/certs/ca.zip -d config/certs;
        fi;
        if [ ! -f config/certs/certs.zip ]; then
          echo "Creating certs";
          echo -ne \
          "instances:"\
          "  - name: es01"\
          "    dns:"\
          "      - es01"\
          "      - localhost"\
          "    ip:"\
          "      - 127.0.0.1"\
          "  - name: kibana"\
          "    dns:"\
          "      - kibana"\
          "      - localhost"\
          "    ip:"\
          "      - 127.0.0.1"\
          "  - name: fleet-server"\
          "    dns:"\
          "      - fleet-server"\
          "      - localhost"\
          "    ip:"\
          "      - 127.0.0.1"\
          > config/certs/instances.yml;
          bin/elasticsearch-certutil cert --silent --pem -out config/certs/certs.zip --in config/certs/instances.yml --ca-cert config/certs/ca/ca.crt --ca-key config/certs/ca/ca.key;
          unzip config/certs/certs.zip -d config/certs;
        fi;
        echo "Setting file permissions"
        chown -R root:root config/certs;
        find . -type d -exec chmod 750 ;;
        find . -type f -exec chmod 640 ;; 
        echo "Waiting for Elasticsearch availability";
        until curl -s --cacert config/certs/ca/ca.crt https://es01:9200 | grep -q "missing authentication credentials"; do sleep 30; done;
        echo "Setting kibana_system password";
        until curl -s -X POST --cacert config/certs/ca/ca.crt -u "elastic:\${ELASTIC_PASSWORD}" -H "Content-Type: application/json" https://es01:9200/_security/user/kibana_system/_password -d "{\"password\":\"\${KIBANA_PASSWORD}\"}" | grep -q "^{}"; do sleep 10; done;
        echo "All done!";
      '
    healthcheck:
      test: ["CMD-SHELL", "[ -f config/certs/es01/es01.crt ]"]
      interval: 1s
      timeout: 5s
      retries: 120

  es01:
    depends_on:
      setup:
        condition: service_healthy
    image: docker.elastic.co/elasticsearch/elasticsearch:\${STACK_VERSION}
    labels:
      co.elastic.logs/module: elasticsearch
    volumes:
      - certs:/usr/share/elasticsearch/config/certs
      - esdata01:/usr/share/elasticsearch/data
    ports:
      - ${ES_PORT}:9200
    environment:
      - node.name=es01
      - cluster.name=\${CLUSTER_NAME}
      - discovery.type=single-node
      - ELASTIC_PASSWORD=\${ELASTIC_PASSWORD}
      - bootstrap.memory_lock=true
      - xpack.security.enabled=true
      - xpack.security.http.ssl.enabled=true
      - xpack.security.http.ssl.key=certs/es01/es01.key
      - xpack.security.http.ssl.certificate=certs/es01/es01.crt
      - xpack.security.http.ssl.certificate_authorities=certs/ca/ca.crt
      - xpack.security.transport.ssl.enabled=true
      - xpack.security.transport.ssl.key=certs/es01/es01.key
      - xpack.security.transport.ssl.certificate=certs/es01/es01.crt
      - xpack.security.transport.ssl.certificate_authorities=certs/ca/ca.crt
      - xpack.security.transport.ssl.verification_mode=certificate
      - xpack.license.self_generated.type=${LICENSE}
    mem_limit: \${ES_MEM_LIMIT}
    ulimits:
      memlock:
        soft: -1
        hard: -1
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "curl -s --cacert config/certs/ca/ca.crt https://localhost:9200 | grep -q 'missing authentication credentials'",
        ]
      interval: 10s
      timeout: 10s
      retries: 120

  kibana:
    depends_on:
      es01:
        condition: service_healthy
    image: docker.elastic.co/kibana/kibana:\${STACK_VERSION}
    labels:
      co.elastic.logs/module: kibana
    volumes:
      - certs:/usr/share/kibana/config/certs
      - kibanadata:/usr/share/kibana/data
      - ./kibana.yml:/usr/share/kibana/config/kibana.yml:ro
    ports:
      - ${KIBANA_PORT}:5601
    environment:
      - SERVERNAME=kibana
      - ELASTICSEARCH_HOSTS=https://es01:9200
      - ELASTICSEARCH_USERNAME=kibana_system
      - ELASTICSEARCH_PASSWORD=${KIBANA_PASSWORD}
      - ELASTICSEARCH_SSL_CERTIFICATEAUTHORITIES=config/certs/ca/ca.crt
      - XPACK_SECURITY_ENCRYPTIONKEY=${ENCRYPTION_KEY}
      - XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY=${ENCRYPTION_KEY}
      - XPACK_REPORTING_ENCRYPTIONKEY=${ENCRYPTION_KEY}
      - XPACK_REPORTING_KIBANASERVER_HOSTNAME=localhost
      - SERVER_SSL_ENABLED=true
      - SERVER_SSL_CERTIFICATE=config/certs/kibana/kibana.crt
      - SERVER_SSL_KEY=config/certs/kibana/kibana.key
      - SERVER_SSL_CERTIFICATEAUTHORITIES=config/certs/ca/ca.crt
      - ELASTIC_APM_SECRET_TOKEN=${ELASTIC_APM_SECRET_TOKEN}
    mem_limit: ${KB_MEM_LIMIT}
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "curl -I -s --cacert config/certs/ca/ca.crt https://localhost:5601 | grep -q 'HTTP/1.1 302 Found'",
        ]
      interval: 10s
      timeout: 10s
      retries: 120

  metricbeat01:
    depends_on:
      es01:
        condition: service_healthy
      kibana:
        condition: service_healthy
    image: docker.elastic.co/beats/metricbeat:${STACK_VERSION}
    user: root
    volumes:
      - certs:/usr/share/metricbeat/certs
      - metricbeatdata01:/usr/share/metricbeat/data
      - "./metricbeat.yml:/usr/share/metricbeat/metricbeat.yml:ro"
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "/sys/fs/cgroup:/hostfs/sys/fs/cgroup:ro"
      - "/proc:/hostfs/proc:ro"
      - "/:/hostfs:ro"
    environment:
      - ELASTIC_USER=elastic
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
      - ELASTIC_HOSTS=https://es01:9200
      - KIBANA_HOSTS=https://kibana:5601
      - LOGSTASH_HOSTS=http://logstash01:9600
      - CA_CERT=certs/ca/ca.crt
      - ES_CERT=certs/es01/es01.crt
      - ES_KEY=certs/es01/es01.key
      - KB_CERT=certs/kibana/kibana.crt
      - KB_KEY=certs/kibana/kibana.key
    command:
      -strict.perms=false

  filebeat01:
    depends_on:
      es01:
        condition: service_healthy
    image: docker.elastic.co/beats/filebeat:\${STACK_VERSION}
    user: root
    volumes:
      - certs:/usr/share/filebeat/certs
      - filebeatdata01:/usr/share/filebeat/data
      - "./filebeat_ingest_data/:/usr/share/filebeat/ingest_data/"
      - "./filebeat.yml:/usr/share/filebeat/filebeat.yml:ro"
      - "/var/lib/docker/containers:/var/lib/docker/containers:ro"
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
    environment:
      - ELASTIC_USER=elastic
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
      - ELASTIC_HOSTS=https://es01:9200
      - KIBANA_HOSTS=https://kibana:5601
      - LOGSTASH_HOSTS=http://logstash01:9600
      - CA_CERT=certs/ca/ca.crt
    command:
      -strict.perms=false

  logstash01:
    depends_on:
      es01:
        condition: service_healthy
      kibana:
        condition: service_healthy
    image: docker.elastic.co/logstash/logstash:\${STACK_VERSION}
    labels:
      co.elastic.logs/module: logstash
    user: root
    volumes:
      - certs:/usr/share/logstash/certs
      - logstashdata01:/usr/share/logstash/data
      - "./logstash_ingest_data/:/usr/share/logstash/ingest_data/"
      - "./logstash.conf:/usr/share/logstash/pipeline/logstash.conf:ro"
    environment:
      - xpack.monitoring.enabled=false
      - ELASTIC_USER=elastic
      - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
      - ELASTIC_HOSTS=https://es01:9200

  fleet-server:
    depends_on:
      kibana:
        condition: service_healthy
      es01:
        condition: service_healthy
    image: docker.elastic.co/beats/elastic-agent:\${STACK_VERSION}
    volumes:
      - certs:/certs
      - fleetserverdata:/usr/share/elastic-agent
      - "/var/lib/docker/containers:/var/lib/docker/containers:ro"
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "/sys/fs/cgroup:/hostfs/sys/fs/cgroup:ro"
      - "/proc:/hostfs/proc:ro"
      - "/:/hostfs:ro"
    ports:
      - ${FLEET_PORT}:8220
      - ${APMSERVER_PORT}:8200
    user: root
    environment:
      - SSL_CERTIFICATE_AUTHORITIES=/certs/ca/ca.crt
      - CERTIFICATE_AUTHORITIES=/certs/ca/ca.crt
      - FLEET_CA=/certs/ca/ca.crt
      - FLEET_ENROLL=1
      - FLEET_INSECURE=true
      - FLEET_SERVER_ELASTICSEARCH_CA=/certs/ca/ca.crt
      - FLEET_SERVER_ELASTICSEARCH_HOST=https://es01:9200
      - FLEET_SERVER_ELASTICSEARCH_INSECURE=true
      - FLEET_SERVER_ENABLE=1
      - FLEET_SERVER_CERT=/certs/fleet-server/fleet-server.crt
      - FLEET_SERVER_CERT_KEY=/certs/fleet-server/fleet-server.key
      - FLEET_SERVER_INSECURE_HTTP=true
      - FLEET_SERVER_POLICY_ID=fleet-server-policy
      - FLEET_URL=https://fleet-server:8220
      - KIBANA_FLEET_CA=/certs/ca/ca.crt
      - KIBANA_FLEET_SETUP=1
      - KIBANA_FLEET_USERNAME=elastic
      - KIBANA_FLEET_PASSWORD=\${ELASTIC_PASSWORD}
      - KIBANA_HOST=https://kibana:5601

  webapp:
    build:
      context: app
    volumes:
      - "/var/lib/docker/containers:/var/lib/docker/containers:ro"
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "/sys/fs/cgroup:/hostfs/sys/fs/cgroup:ro"
      - "/proc:/hostfs/proc:ro"
      - "/:/hostfs:ro"
    ports:
      - 8000:8000
'''

    with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
        temp_file.write(docker_compose_content)
        temp_file_path = temp_file.name

    sftp = ssh.open_sftp()
    print(base_path)
    print(f'{base_path}/core/elkstack/docker-compose.yml')
    sftp.put(temp_file_path, f'{base_path}/core/elkstack/docker-compose.yml')
    sftp.close()
    os.remove(temp_file_path)

    log_output(f"Created docker-compose.yml at {base_path}/core/elkstack/docker-compose.yml", logfile)


def create_env_file(ssh, base_path, logfile):
    env_content = '''
# Project namespace (defaults to the current folder name if not set)
COMPOSE_PROJECT_NAME=es

# Password for the 'elastic' user (at least 6 characters)
ELASTIC_PASSWORD=changeme

# Password for the 'kibana_system' user (at least 6 characters)
KIBANA_PASSWORD=changeme

# Version of Elastic products
#https://www.elastic.co/downloads/past-releases#elasticsearch
STACK_VERSION=8.8.2

# Set the cluster name
CLUSTER_NAME=docker-cluster

# Set to 'basic' or 'trial' to automatically start the 30-day trial
LICENSE=basic
#LICENSE=trial

# Port to expose Elasticsearch HTTP API to the host
ES_PORT=9200

# Port to expose Kibana to the host
KIBANA_PORT=5601

# Port to expose Fleet to the host
FLEET_PORT=8220

# Port to expose APM to the host
APMSERVER_PORT=8200

# APM Secret Token for POC environments only
ELASTIC_APM_SECRET_TOKEN=supersecrettoken

# Increase or decrease based on the available host memory (in bytes)
ES_MEM_LIMIT=3073741824
KB_MEM_LIMIT=1073741824
LS_MEM_LIMIT=1073741824

# SAMPLE Predefined Key only to be used in POC environments
ENCRYPTION_KEY=c34d38b3a14956121ff2170e5030b471551370178f43e5626eec58b04a30fae2
'''

    with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
        temp_file.write(env_content)
        temp_file_path = temp_file.name

    sftp = ssh.open_sftp()
    sftp.put(temp_file_path, f'/{base_path}/core/elkstack/.env')
    sftp.close()
    os.remove(temp_file_path)

    log_output(f"Created .env file at /{base_path}/core/elkstack/.env", logfile)

def create_logstash_config(ssh, base_path, logfile):
    logstash_config_content = '''
input {
  file {
    #https://www.elastic.co/guide/en/logstash/current/plugins-inputs-file.html
    #default is TAIL which assumes more data will come into the file.
    #change to mode => "read" if the file is a compelte file.  by default, the file will be removed once reading is complete -- backup your files if you need them.
    mode => "tail"
    path => "/usr/share/logstash/ingest_data/*"
  }
}

filter {
}

output {
  elasticsearch {
    index => "logstash-%{+YYYY.MM.dd}"
    hosts=> "${ELASTIC_HOSTS}"
    user=> "${ELASTIC_USER}"
    password=> "${ELASTIC_PASSWORD}"
    cacert=> "certs/ca/ca.crt"
  }
}
'''

    with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
        temp_file.write(logstash_config_content)
        temp_file_path = temp_file.name

    sftp = ssh.open_sftp()
    sftp.put(temp_file_path, f'/{base_path}/core/elkstack/logstash.conf')
    sftp.close()
    os.remove(temp_file_path)

    log_output(f"Created logstash.conf at /{base_path}/core/elkstack/logstash.conf", logfile)

def create_filebeat_config(ssh, base_path, logfile):
    filebeat_config_content = '''
filebeat.inputs:
- type: filestream
  id: default-filestream
  paths:
    - ingest_data/*.log

filebeat.autodiscover:
  providers:
    - type: docker
      hints.enabled: true

processors:
- add_docker_metadata: ~

setup.kibana:
  host: ${KIBANA_HOSTS}
  username: ${ELASTIC_USER}
  password: ${ELASTIC_PASSWORD} 

output.elasticsearch:
  hosts: ${ELASTIC_HOSTS}
  username: ${ELASTIC_USER}
  password: ${ELASTIC_PASSWORD}
  ssl:
    enabled: true
    certificate_authorities: ${CA_CERT}
'''

    with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
        temp_file.write(filebeat_config_content)
        temp_file_path = temp_file.name

    sftp = ssh.open_sftp()
    sftp.put(temp_file_path, f'/{base_path}/core/elkstack/filebeat.yml')
    sftp.close()
    os.remove(temp_file_path)

    log_output(f"Created filebeat.yml at /{base_path}/core/elkstack/filebeat.yml", logfile)

def create_kibana_config(ssh, base_path, logfile):
    kibana_config_content = '''
elastic:
  apm:
    active: true
    serverUrl: "http://fleet-server:8200"
    secretToken: ${ELASTIC_APM_SECRET_TOKEN}
server.host: "0.0.0.0"
telemetry.enabled: "true"
xpack.fleet.packages:
  - name: fleet_server
    version: latest
  - name: system
    version: latest
  - name: elastic_agent
    version: latest
  - name: apm
    version: latest
xpack.fleet.agentPolicies:
  - name: Fleet-Server-Policy
    id: fleet-server-policy
    namespace: default
    monitoring_enabled: 
      - logs
      - metrics
    package_policies:
      - name: fleet_server-1
        package:
          name: fleet_server
      - name: system-1
        package:
          name: system
      - name: elastic_agent-1
        package:
          name: elastic_agent
      - name: apm-1
        package:
          name: apm
        inputs:
        - type: apm
          enabled: true
          vars:
          - name: host
            value: 0.0.0.0:8200
          - name: secret_token
            value: ${ELASTIC_APM_SECRET_TOKEN}
'''

    with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
        temp_file.write(kibana_config_content)
        temp_file_path = temp_file.name

    sftp = ssh.open_sftp()
    sftp.put(temp_file_path, f'/{base_path}/core/elkstack/kibana.yml')
    sftp.close()
    os.remove(temp_file_path)

    log_output(f"Created kibana.yml at /{base_path}/core/elkstack/kibana.yml", logfile)

def create_metricbeat_config(ssh, base_path, logfile):
    metricbeat_config_content = '''
metricbeat.config.modules:
  path: ${path.config}/modules.d/*.yml
  reload.enabled: false

metricbeat.modules:
- module: elasticsearch
  xpack.enabled: true
  period: 10s
  hosts: ${ELASTIC_HOSTS}
  username: ${ELASTIC_USER}
  password: ${ELASTIC_PASSWORD}
  ssl:
    enabled: true
    certificate_authorities: ${CA_CERT}

- module: logstash
  xpack.enabled: true
  period: 10s
  hosts: ${LOGSTASH_HOSTS}

- module: kibana
  metricsets: 
    - stats
  period: 10s
  hosts: ${KIBANA_HOSTS}
  username: ${ELASTIC_USER}
  password: ${ELASTIC_PASSWORD}
  xpack.enabled: true
  ssl:
    enabled: true
    certificate_authorities: ${CA_CERT}

- module: docker
  metricsets:
    - "container"
    - "cpu"
    - "diskio"
    - "healthcheck"
    - "info"
    #- "image"
    - "memory"
    - "network"
  hosts: ["unix:///var/run/docker.sock"]
  period: 10s
  enabled: true

processors:
  - add_host_metadata: ~
  - add_docker_metadata: ~

output.elasticsearch:
  hosts: ${ELASTIC_HOSTS}
  username: ${ELASTIC_USER}
  password: ${ELASTIC_PASSWORD}
  ssl:
    enabled: true
    certificate_authorities: ${CA_CERT}
'''

    with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
            temp_file.write(metricbeat_config_content)
            temp_file_path = temp_file.name

    sftp = ssh.open_sftp()
    sftp.put(temp_file_path, f'/{base_path}/core/elkstack/metricbeat.yml')
    sftp.close()
    os.remove(temp_file_path)

    log_output(f"Created metricbeat.yml at /{base_path}/core/elkstack/metricbeat.yml", logfile)


