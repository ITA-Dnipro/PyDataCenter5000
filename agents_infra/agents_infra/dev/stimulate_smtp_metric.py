import logging
import os
import sys
import threading

from agents_infra.agents.smtp.smtp import SMTPAgent

# Add the root directory to sys.path
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
)


# Simulate CPU load
def start_cpu_stress():
    for i in range(10):
        print(i)


# Simulate RAM load
def ram_stress():
    _ = ['x' * 1024 * 1024 for _ in range(100)]  # Allocate ~100MB temporarily


# Simulate disk activity
def disk_stress(file_path='/tmp/stress_test_file.txt'):
    with open(file_path, 'w') as f:
        for _ in range(10000):
            f.write('stress test line\n')


if __name__ == '__main__':
    agent = SMTPAgent()

    # Create logger
    logger = logging.getLogger('metrics')
    logger.setLevel(logging.INFO)

    # Create file handler
    log_file_path = os.path.join(
        os.path.dirname(__file__),
        '../smtp/logs/agent.log'
    )
    fh = logging.FileHandler(log_file_path)
    fh.setLevel(logging.INFO)

    # Create formatter and add to handler
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    fh.setFormatter(formatter)

    if not logger.handlers:
        logger.addHandler(fh)
    logger.propagate = False

    # Simulate system load
    cpu_thread = threading.Thread(target=start_cpu_stress)
    ram_thread = threading.Thread(target=ram_stress)
    disk_thread = threading.Thread(target=disk_stress)

    cpu_thread.start()
    ram_thread.start()
    disk_thread.start()

    cpu_thread.join()  # Wait for CPU load to finish

    # Generate and log the report
    result = agent.generate_report()
    logger.info('Generated report: %s', result)

    # Clean up disk stress file
    try:
        os.remove('/tmp/stress_test_file.txt')
    except OSError:
        pass
