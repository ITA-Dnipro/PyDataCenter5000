"""
Universal critical-process monitor for any ServerAgent.

Usage:
    python critical_processes_check.py <agent_type> [--interval N]

Example:
    python critical_processes_check.py ntp --interval 5
"""

import argparse
import logging
import os
import sys
import threading
import time

from agents.agent import ServerAgent  # for type‐checking only


def import_agent_class(agent_type):
    """
    Dynamically import and return the Agent class for a given type.

    Args:
        agent_type (str): Lowercase name of the agent module,
        e.g. 'ntp', 'dns', 'smtp'.

    Returns:
        type: The Agent subclass (e.g. NTPAgent, DNSAgent).

    Raises:
        ImportError: If the module cannot be imported.
        AttributeError: If the expected class is not found in the module.
    """
    module_name = 'agents.{0}.{0}'.format(agent_type)
    class_name = '{0}Agent'.format(agent_type.upper())
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)


def monitor_processes(agent, interval, stop_event):
    """
    Run in a background thread: periodically check each critical process
    and overall service health, log state transitions, and attempt restarts.

    Args:
        agent (ServerAgent): Initialized agent instance.
        interval (int): Seconds between each health check iteration.
        stop_event (threading.Event): Event to signal clean shutdown.
    """
    logger = agent.logger
    last_status = {}

    # Initial per-process check
    for proc in agent.critical_processes:
        up = agent._is_process_running(proc_name=proc)
        last_status[proc] = up
        if up:
            logger.info('%s is RUNNING', proc)
        else:
            logger.warning('%s is DOWN', proc)

    # Initial overall service health
    last_health = agent.is_service_healthy()
    if last_health:
        logger.info('Service is HEALTHY')
    else:
        logger.warning('Service is UNHEALTHY. Attempting restart...')
        agent.maybe_restart_service()

    # Monitoring loop
    while not stop_event.is_set():
        time.sleep(interval)

        # Check transitions for each process
        for proc in agent.critical_processes:
            up = agent._is_process_running(proc_name=proc)
            prev = last_status.get(proc, False)
            if prev and not up:
                logger.warning('%s is DOWN', proc)
            elif not prev and up:
                logger.info('%s has RECOVERED', proc)
            last_status[proc] = up

        # Check overall service transition
        healthy = agent.is_service_healthy()
        if healthy != last_health:
            if healthy:
                logger.info('Service has RECOVERED and is HEALTHY')
            else:
                logger.warning('Service is UNHEALTHY. Attempting restart...')
                agent.maybe_restart_service()
            last_health = healthy

    logger.info('Monitor thread exiting')


def main():
    """
    Entry point: parse CLI args, instantiate the chosen Agent,
    configure logging, launch the monitoring thread, and wait for CTRL+C.
    """
    parser = argparse.ArgumentParser(
        description='Universal critical-process monitor'
    )
    parser.add_argument(
        'agent_type',
        choices=['ntp', 'dns', 'smtp'],
        help='Which agent to monitor'
    )
    parser.add_argument(
        '--interval', '-i',
        type=int,
        default=int(os.getenv('MONITOR_INTERVAL', '10')),
        help='Seconds between health checks (env MONITOR_INTERVAL)'
    )
    args = parser.parse_args()

    # Dynamically load and instantiate the agent
    AgentClass = import_agent_class(args.agent_type)
    agent = AgentClass.from_config_file()
    agent.collect_server_metadata()

    # Configure logging via the agent's built-in method
    agent.setup_logging()
    logger = agent.logger

    # Fallback console handler if none configured
    if not logger.handlers:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(
            logging.Formatter(
                '%(asctime)s %(name)s %(levelname)s: %(message)s'
            )
        )
        logger.addHandler(console)

    # Start the monitor thread
    stop_event = threading.Event()
    monitor_thread = threading.Thread(
        target=monitor_processes,
        args=(agent, args.interval, stop_event),
        name='{0}-monitor'.format(args.agent_type)
    )
    monitor_thread.setDaemon(True)
    monitor_thread.start()

    logger.info(
        'Monitoring %s critical processes every %ds...',
        args.agent_type, args.interval
    )

    # Keep main thread alive until interrupted
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info('Interrupted, stopping monitor...')
        stop_event.set()
        monitor_thread.join(5)
        logger.info('Monitor shutdown complete')
        sys.exit(0)


if __name__ == '__main__':
    main()
