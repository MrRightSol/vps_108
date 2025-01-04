from datetime import datetime

def create_log_file():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_filename = f'vps_setup_log_{timestamp}.txt'
    return open(log_filename, 'w')

def log_output(output, logfile):
    logfile.write(output + '\n')
