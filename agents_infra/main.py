import logging
import time

logger = logging.getLogger(__name__)


def main():
    logging.info('agents-infra started. Press Ctrl+C to exit.')

    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info('Interrupting...')
    finally:
        logging.info('agents-infra exiting...')


if __name__ == '__main__':
    main()
