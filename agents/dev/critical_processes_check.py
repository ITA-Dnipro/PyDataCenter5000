import logging.config
import os
import sys
import threading
import time

from agents.ntp.ntp import NTPAgent

# Configure logging via ini file
conf_path = os.path.join(
    os.path.dirname(__file__),
    '../utils/logconfig.ini'
)

logging.config.fileConfig(
    conf_path,
    defaults={
        'agent_name': 'ntp',
        'log_path': 'ntp.log',
    }
)

logger = logging.getLogger('ntp')


def monitor_processes(agent, interval, stop_event):
    """
    Periodically checks the status of each critical process and overall
    service health for the provided agent.

    Logs the status of each critical process (RUNNING/DOWN/RECOVERED)
    and performs service health check using agent.is_service_healthy().
    If the service is unhealthy,
    attempts a restart via maybe_restart_service().

    Args:
        agent (NTPAgent): The agent instance to monitor.
        interval (int): Time in seconds between checks.
        stop_event (threading.Event): Event to signal stopping the thread.

    Returns:
        None
    """
    last_status = {}

    # Initial status check for critical processes
    for proc in agent.critical_processes:
        agent.processes = [proc]
        up = agent._is_process_running()
        last_status[proc] = up
        if up:
            logger.info('%s is RUNNING', proc)
        else:
            logger.warning('%s is DOWN', proc)

    # Periodic monitoring loop
    while not stop_event.is_set():
        time.sleep(interval)

        # Check each critical process
        for proc in agent.critical_processes:
            agent.processes = [proc]
            up = agent._is_process_running()
            prev = last_status.get(proc, False)

            if prev and not up:
                logger.warning('%s is DOWN', proc)
            elif not prev and up:
                logger.info('%s has RECOVERED', proc)

            last_status[proc] = up

        # Check overall service health
        healthy = agent.is_service_healthy()
        if healthy:
            logger.info('NTP service is healthy.')
        else:
            logger.warning('NTP service is UNHEALTHY. Attempting restart...')
            agent.maybe_restart_service()

    logger.info('Monitor thread exiting')


def main():
    """
    Main entry point for the process monitoring script.

    Initializes the NTP agent, starts the monitoring thread, and keeps
    the main thread alive until interrupted by the user.

    Returns:
        None
    """
    agent = NTPAgent.from_config_file()
    agent.collect_server_metadata()

    stop_event = threading.Event()
    t = threading.Thread(
        target=monitor_processes,
        args=(agent, 10, stop_event),
        name='ntp-monitor'
    )
    t.setDaemon(True)
    t.start()

    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Interrupted, stopping monitor...')
        stop_event.set()
        t.join(5)
        sys.exit(0)


if __name__ == '__main__':
    main()
