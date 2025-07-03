import logging
import os
import signal
import sys


def main():
    sys.path.insert(
        0,
        os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    )

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if len(sys.argv) != 2:
        logging.error('Usage: python run_http_server.py <agent_name>')
        sys.exit(1)

    agent_name = sys.argv[1]

    try:
        module_path = 'agents_infra.agents.%s.%s' % (agent_name, agent_name)
        module = __import__(module_path, fromlist=[''])

        if agent_name.lower() == 'web':
            agent_class = getattr(module, 'WebAgent')
        else:
            agent_class = getattr(module, agent_name.upper() + 'Agent')

        config_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'agents',
            agent_name,
            'config.ini'
        )
        config_path = os.path.abspath(config_path)

        if os.path.exists(config_path):
            logging.info('Loading agent from config file: %s' % config_path)
            agent = agent_class.from_config_file(filename=config_path)
        else:
            logging.warning('No config file found; using default constructor.')
            agent = agent_class()

        try:
            agent.setup_logging()
        except AttributeError:
            logging.debug('Agent does not implement setup_logging().')

        logging.info('Agent initialized. Collecting server metadata...')
        agent.collect_server_metadata()

        health_manager_module = __import__(
            'agents_infra.managers.health_server_manager', fromlist=['']
        )
        HealthServerManager = getattr(
            health_manager_module, 'HealthServerManager'
        )

        supervisor_module = __import__(
            'agents_infra.supervisor', fromlist=['']
        )
        AgentSupervisor = getattr(supervisor_module, 'AgentSupervisor')

        health_manager = HealthServerManager(agent=agent)
        supervisor = AgentSupervisor(agent=agent, managers=[health_manager])

        supervisor.schedule_exit(min_delay=1, max_delay=3)

        def start_health_server():
            health_manager.start()

        supervisor.schedule(
            start_health_server,
            max_retries=1,
            weak=False,
        )

        logging.info('Supervisor started, event loop running...')
        supervisor.start()

    except Exception as e:
        logging.exception('Error while running agent: %s', e)
        sys.exit(1)


if __name__ == '__main__':
    main()
