from logtools import maybe_log_message

from ..utils.network import check_http_health, is_tcp_reachable
from ..utils.timestamp import get_current_time

revert_interval = 900


class AgentCommunication(object):
    def __init__(self, auth_token, post_data_fn, logger, controller_urls):
        """
        Initialize with a unique server name and a callable for posting data.
        """
        self.post_data = post_data_fn
        self.auth_token_type = 'Bearer'
        self.logger = logger
        self.controller_urls = controller_urls
        self.current_controller = controller_urls[0]

    def _ping_controller(self, url, api_key, timeout=3):
        if not is_tcp_reachable(url, timeout):
            maybe_log_message(
                'Controller unreachable at TCP level: %s' % url,
                logger=self.logger
            )
            return False

        healthy = check_http_health(
            url,
            api_key,
            self.auth_token_type,
            timeout
        )
        if not healthy:
            maybe_log_message(
                'Health check failed for controller: %s' % url,
                logger=self.logger
            )
        return healthy

    def _find_healthy_controller(self, urls, api_key):
        for url in urls:
            if self._ping_controller(url, api_key=api_key):
                return url
        return None

    def _switch_controller(self, new_url):
        maybe_log_message(
            'Controller switched: %s -> %s' % (
                self.current_controller,
                new_url
            ),
            logger=self.logger
        )
        self.current_controller = new_url
        self.last_success_time = get_current_time()

    def ensure_active_controller(self, api_key):
        """
        Ensure there is a healthy active controller.
        """
        if self._attempt_revert_to_primary(api_key):
            return self.current_controller

        if self._ping_controller(self.current_controller, api_key=api_key):
            return self.current_controller

        remaining_urls = self._get_lower_priority_urls()
        healthy_url = self._find_healthy_controller(remaining_urls, api_key)
        if healthy_url:
            self._switch_controller(healthy_url)
            return healthy_url

        self.logger.error('No available controller. All health checks failed.')
        return None

    def try_revert_primary_controller(self, api_key):
        """
        Attempt to revert to the primary controller.
        """
        if self.current_controller == self.controller_urls[0]:
            return self.current_controller

        elapsed = get_current_time() - self.last_success_time
        if elapsed < revert_interval:
            return self.current_controller

        higher_priority_urls = self._get_higher_priority_urls()
        healthy_url = self._find_healthy_controller(
            higher_priority_urls,
            api_key
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

    def _attempt_revert_to_primary(self, api_key):
        previous = self.current_controller
        self.try_revert_primary_controller(api_key)
        return previous != self.current_controller

    def _get_higher_priority_urls(self):
        current_index = self.controller_urls.index(self.current_controller)
        return self.controller_urls[:current_index]

    def _get_lower_priority_urls(self):
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
        Ensure active controller, then delegate to post_data_fn.

        Args:
            endpoint (str): The API endpoint path (e.g. 'status/update').
            payload (dict or str): The data to send.
            api_key (str, optional): API key to use for auth.
            max_retries, delay, timeout, fail_silently: Passed through.
            **headers: Additional headers.
        Returns:
            Response object or None.
        """
        controller_url = self.ensure_active_controller(api_key)
        if controller_url is None:
            self.logger.error('No healthy controller available.')
            return None

        return self.post_data(
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
