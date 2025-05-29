import tempfile

import mock
import pytest

from agents.agent import ServerAgent


class MockAgent(ServerAgent):

    def __init__(
        self,
        server_name='mock',
        port=None,
        processes=None,
        controller_url=None,
        config_file=None,
    ):
        super(MockAgent, self).__init__(
            server_name, port, processes, controller_url, config_file
        )


def test_type_checks_on_init():
    with pytest.raises(TypeError):
        MockAgent(port='invalid')

    with pytest.raises(TypeError):
        MockAgent(processes=0)


def test_type_checks_on_config_parse():
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write('[server]\nname=mock\nport=invalid\nprocesses=proc1')
        tmp.flush()

        with pytest.raises(TypeError):
            MockAgent.from_config_file(tmp.name)


def test_status_to_controller_success():
    def mock_urlopen(request, timeout=5):
        class MockResponse(object):
            def getcode(self):
                return 201
        return MockResponse()

    with tempfile.NamedTemporaryFile() as tmp:
        agent = MockAgent(port=12345)
        agent.setup_logging(tmp.name)
        agent.collect_server_metadata()

        agent.controller_url = 'http://mock/api/status/'

        with mock.patch('urllib2.urlopen', mock_urlopen):
            agent.status_to_controller()

        tmp.seek(0)
        contents = tmp.read()

        assert 'POST request status: 201' in contents, (
            'Expected "POST request status: 201" in logs, got:\n%s' % contents
        )
