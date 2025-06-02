import pkg_resources

from ..agent import ServerAgent


class SMTPAgent(ServerAgent):

    def __init__(
        self,
        server_name='smtp',
        port=25,
        processes=None,
        interface=None,
        protocol='tcp',
        controller_url=None,
    ):
        super(SMTPAgent, self).__init__(
            server_name=server_name,
            port=port,
            processes=processes or ['postfix', 'exim', 'sendmail', 'master'],
            interface=interface,
            protocol=protocol,
            controller_url=controller_url,
        )

    def service_healthy(self, timeout=2):
        # TODO: add SMTP specific check (send EHLO command).
        return self.is_process_running() and self.is_port_open(timeout=timeout)
