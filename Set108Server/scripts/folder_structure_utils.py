import paramiko
import os
import json
from scripts.logging_utils import log_output

def create_folder_structure(ssh, structure, base_path, logfile):

    for key, value in structure.items():
        current_path = os.path.join(base_path, key).replace('\\', '/')
        if isinstance(value, dict):
            # Create the directory
            command = f'mkdir -p {current_path}'
            log_output(f"Creating directory: {current_path}", logfile)
            stdin, stdout, stderr = ssh.exec_command(command)
            stdout.channel.recv_exit_status()
            log_output(stdout.read().decode(), logfile)
            log_output(stderr.read().decode(), logfile)
            # Recursively create the substructure
            create_folder_structure(ssh, value, current_path, logfile)
        elif isinstance(value, list) and key == "files":
            for file in value:
                file_path = os.path.join(base_path, file).replace('\\', '/')
                command = f'touch {file_path}'
                log_output(f"Creating file: {file_path}", logfile)
                stdin, stdout, stderr = ssh.exec_command(command)
                stdout.channel.recv_exit_status()
                log_output(stdout.read().decode(), logfile)
                log_output(stderr.read().decode(), logfile)
