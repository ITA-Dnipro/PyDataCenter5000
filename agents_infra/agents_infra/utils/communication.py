import logging
import socket
import threading

import urllib2
from logtools import maybe_log_message

from ..utils.network import (check_http_health, find_first_healthy_url,
                             is_tcp_reachable, ping_url)
from ..utils.timestamp import get_current_time


class AgentCommunication(object):
    """
    Handles communication between an agent and its controller(s),
    including health checks, failover logic, and posting data.
    """

    def __init__(
        self,
        auth_token_type,
        post_data_fn,
        controller_urls,
        get_data_fn=None,
        revert_interval=900
    ):
        """
        Initialize AgentCommunication.

        Args:
            auth_token_type (str): Type of auth token to use in requests.
            post_data_fn (callable): Function to send data to a controller.
            get_data_fn (callable, optional): Function to get data from
            a controller.
            controller_urls (list): List of controller URLs in priority order.
        """
        self.post_data_fn = post_data_fn
        self.get_data_fn = get_data_fn
        self.auth_token_type = auth_token_type
        self.controller_urls = controller_urls
        if not self.controller_urls:
            self.current_controller = None
            maybe_log_message(
                'Controller urls are not set',
                logger=self.logger,
                level=logging.INFO
            )
        else:
            self.current_controller = controller_urls[0]
        self.revert_interval = revert_interval
        self.last_success_time = get_current_time()
        self.controller_lock = threading.Lock()

    @property
    def logger(self):
        """
        Returns a logger named after the agent config or falls back
        to 'agent-communication'.
        """
        name = 'agent-communication'
        if hasattr(self.post_data_fn.__self__.config, 'name'):
            name = self.post_data_fn.__self__.config.name
        return logging.getLogger(name)

    def _switch_controller(self, new_url):
        """
        Switch the current controller to a new one.
        """
        old_url = self.current_controller
        self.current_controller = new_url
        self.last_success_time = get_current_time()
        maybe_log_message(
            'Controller switched: %s -> %s' %
            (old_url, self.current_controller),
            logger=self.logger,
            level=logging.INFO
        )

    def ensure_active_controller(self, api_key):
        """
            Ensure there is an active, healthy controller.

            Returns:
                str or None: Active controller URL,
                or None if none are healthy.
        """

        # Acquire lock to safely read/update current_controller
        self.controller_lock.acquire()
        try:
            self.current_controller = (
                self.attempt_revert_to_primary_controller(api_key=api_key)
            )
            current = self.current_controller
        finally:
            self.controller_lock.release()

        # Perform health check outside the lock
        try:
            if ping_url(current, api_key=api_key, logger=self.logger,
                        auth_token_type=self.auth_token_type):
                return current
        except Exception as e:
            maybe_log_message(
                'Exception during ping_url '
                'for controller %s: %s' % (current, str(e)),
                logger=self.logger
            )

        remaining_urls = self._get_lower_priority_urls()
        healthy_url = find_first_healthy_url(
            urls=remaining_urls,
            api_key=api_key,
            auth_token_type=self.auth_token_type,
            logger=self.logger
        )

        if healthy_url:
            self.controller_lock.acquire()
            try:
                self._switch_controller(healthy_url)
            finally:
                self.controller_lock.release()
            return healthy_url

        maybe_log_message(
            'No available controller. All health checks failed.',
            logger=self.logger
        )
        return None

    def attempt_revert_to_primary_controller(self, api_key):
        """
        Attempt to revert back to the primary controller if healthy.

        Returns:
            str: Current controller URL after the check.
        """
        if not self.controller_urls:
            maybe_log_message(
                'No controller URLs configured. Cannot attempt revert.',
                logger=self.logger,
                level=logging.WARNING
            )
            return None

        if self.current_controller == self.controller_urls[0]:
            return self.current_controller

        elapsed = get_current_time() - self.last_success_time
        if elapsed < self.revert_interval:
            return self.current_controller

        higher_priority_urls = self._get_higher_priority_urls()
        if not higher_priority_urls:
            maybe_log_message(
                'No higher-priority controllers to check for reversion.',
                logger=self.logger,
                level=logging.INFO
            )
            return self.current_controller

        healthy_url = find_first_healthy_url(
            higher_priority_urls,
            api_key,
            auth_token_type=self.auth_token_type,
            logger=self.logger
        )

        if healthy_url:
            maybe_log_message(
                'Reverting controller: %s -> %s' %
                (self.current_controller, healthy_url),
                logger=self.logger
            )
            self._switch_controller(healthy_url)

        return self.current_controller

    def _get_higher_priority_urls(self):
        """
        Get controllers with higher priority than the current one.

        Returns:
            list: URLs with higher priority.
        """
        current_index = self.controller_urls.index(self.current_controller)
        return self.controller_urls[:current_index]

    def _get_lower_priority_urls(self):
        """
        Get controllers with lower priority than the current one.

        Returns:
            list: URLs with lower priority.
        """
        current_index = self.controller_urls.index(self.current_controller)
        return self.controller_urls[current_index + 1:]

    def _update_post_data_config(self, controller_url):
        """
        Updates the config of the object that owns post_data_fn,
        if applicable.
        """
        try:
            config = getattr(self.post_data_fn.__self__, 'config', None)
            if config:
                config.current_controller = controller_url
                config.auth_token_type = self.auth_token_type
        except AttributeError:
            maybe_log_message(
                'Failed to update post_data_fn config.',
                logger=self.logger,
                level=logging.WARNING
            )

    def post_data(
        self,
        endpoint,
        payload,
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
        fail_silently=True,
        **headers
    ):
        """
        Post data to the active controller.

        Attempts to send a payload to the specified endpoint of
        the currently active controller.
        Handles controller failover and updates internal controller metadata.

        Args:
            endpoint (str): The API endpoint (relative path) to send
            the data to.
            payload (dict): The JSON-serializable data to be sent
            in the request body.
            api_key (str, optional): API key used
            for authentication (if applicable).
            max_retries (int, optional): Number of retry
            attempts on failure. Default is 3.
            delay (int, optional): Delay (in seconds) between
            retry attempts. Default is 5.
            timeout (int, optional): Timeout (in seconds) for
            the request. Default is 5.
            fail_silently (bool, optional): If True, suppress exceptions and
            return None on failure.
            **headers: Additional HTTP headers to include in the request
            (e.g., `Content-Type`, `Authorization`, custom headers).

        Returns:
            Response object or None: The result of the `post_data_fn` call,
            or None if the controller is unavailable or the request
             fails and `fail_silently` is True.
        """
        controller_url = self.ensure_active_controller(api_key)
        if controller_url is None:
            self.logger.error('No healthy controller available.')
            return None

        self._update_post_data_config(controller_url)

        try:
            return self.post_data_fn(
                endpoint,
                payload,
                to_controller=True,
                api_key=api_key,
                max_retries=max_retries,
                delay=delay,
                timeout=timeout,
                fail_silently=fail_silently,
                **headers
            )
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            maybe_log_message(
                'Network error during post_data_fn: %s' % e,
                logger=self.logger,
                level=logging.ERROR
            )
            if not fail_silently:
                raise
        except Exception as e:
            maybe_log_message(
                'Unexpected error in post_data_fn: %s' % e,
                logger=self.logger,
                level=logging.ERROR
            )
            if not fail_silently:
                raise

        return None

    def get_data(
        self,
        endpoint,
        api_key=None,
        max_retries=3,
        delay=5,
        timeout=5,
        fail_silently=True,
        **headers
    ):
        """
        Get data from the active controller.

        Attempts to fetch data from the specified endpoint of
        the currently active controller.
        Handles controller failover and updates internal controller metadata.

        Args:
            endpoint (str): The API endpoint (relative path)
            to fetch data from.
            api_key (str, optional): API key used for authentication
            (if applicable).
            max_retries (int, optional): Number of retry attempts on failure.
            Default is 3.
            delay (int, optional): Delay (in seconds) between retry attempts.
            Default is 5.
            timeout (int, optional): Timeout (in seconds) for the request.
            Default is 5.
            fail_silently (bool, optional): If True, suppress exceptions and
            return None on failure.
            **headers: Additional HTTP headers to include in the request
            (e.g., `Content-Type`, `Authorization`, custom headers).


        Returns:
            Response object or None: The result of the `get_data_fn` call,
            or None if the controller is unavailable or the request fails and
            `fail_silently` is True.
        """
        if self.get_data_fn is None:
            self.logger.error(
                'No get_data_fn provided to AgentCommunication.')
            return None
        controller_url = self.ensure_active_controller(api_key)
        if controller_url is None:
            self.logger.error('No healthy controller available.')
            return None
        self._update_post_data_config(controller_url)
        try:
            return self.get_data_fn(
                endpoint,
                from_controller=True,
                api_key=api_key,
                max_retries=max_retries,
                delay=delay,
                timeout=timeout,
                fail_silently=fail_silently,
                **headers
            )
        except (urllib2.URLError, urllib2.HTTPError, socket.timeout) as e:
            maybe_log_message(
                'Network error during get_data_fn: %s' % e,
                logger=self.logger,
                level=logging.ERROR
            )
            if not fail_silently:
                raise
        except Exception as e:
            maybe_log_message(
                'Unexpected error in get_data_fn: %s' % e,
                logger=self.logger,
                level=logging.ERROR
            )
            if not fail_silently:
                raise
        return None
