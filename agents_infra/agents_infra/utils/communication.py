import logging

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
            revert_interval=900
    ):
        """
        Initialize AgentCommunication.

        Args:
            auth_token_type (str): Type of auth token to use in requests.
            post_data_fn (callable): Function to send data to a controller.
            controller_urls (list): List of controller URLs in priority order.
        """
        self.post_data_fn = post_data_fn
        self.auth_token_type = auth_token_type
        self.controller_urls = controller_urls
        if self.controller_urls is None:
            self.current_controller = None
        else:
            self.current_controller = controller_urls[0]
        self.revert_interval = revert_interval
        self.last_success_time = get_current_time()

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
        self.current_controller = new_url
        self.last_success_time = get_current_time()
        maybe_log_message(
            'Controller switched: %s -> %s' % (
                self.current_controller,
                new_url
            ),
            logger=self.logger,
            level=logging.INFO
        )

    def ensure_active_controller(self, api_key):
        """
        Ensure there is an active, healthy controller.

        Returns:
            str or None: Active controller URL, or None if none are healthy.
        """
        if self.current_controller != self.controller_urls[0]:
            self.current_controller = self.try_revert_primary_controller(
                api_key=api_key
            )

        if ping_url(
                self.current_controller,
                api_key=api_key,
                logger=self.logger,
                auth_token_type=self.auth_token_type
        ):
            return self.current_controller

        remaining_urls = self._get_lower_priority_urls()
        healthy_url = find_first_healthy_url(
            urls=remaining_urls,
            api_key=api_key,
            auth_token_type=self.auth_token_type,
            logger=self.logger
        )
        if healthy_url:
            self._switch_controller(healthy_url)
            return healthy_url

        maybe_log_message(
            'No available controller. All health checks failed.',
            logger=self.logger
        )
        return None

    def try_revert_primary_controller(self, api_key):
        """
        Attempt to revert back to the primary controller if healthy.

        Returns:
            str: Current controller URL after the check.
        """
        if self.current_controller == self.controller_urls[0]:
            return self.current_controller

        elapsed = get_current_time() - self.last_success_time
        if elapsed < self.revert_interval:
            return self.current_controller

        higher_priority_urls = self._get_higher_priority_urls()
        healthy_url = find_first_healthy_url(
            higher_priority_urls,
            api_key,
            auth_token_type=self.auth_token_type,
            logger=self.logger
        )
        if healthy_url:
            maybe_log_message(
                'Reverting controller: %s -> %s' % (
                    self.current_controller,
                    healthy_url
                ),
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
        """
        controller_url = self.ensure_active_controller(api_key)
        if controller_url is None:
            self.logger.error('No healthy controller available.')
            return None

        if hasattr(self.post_data_fn.__self__, 'config'):
            (self.post_data_fn.__self__.
             config).current_controller = controller_url
            (self.post_data_fn.__self__.
             config).auth_token_type = self.auth_token_type

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
