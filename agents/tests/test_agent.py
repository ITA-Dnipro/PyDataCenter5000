import tempfile

import mock
import pytest
import urllib2

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
    """Test that type checks fail initialization with bad parameters."""
    with pytest.raises(TypeError):
        MockAgent(port='invalid')

    with pytest.raises(TypeError):
        MockAgent(processes=0)


def test_type_checks_on_config_parse():
    """
    Test that type checks fail initialization with bad config file
    parameters.
    """
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write('[server]\nname=mock\nport=invalid\nprocesses=proc1')
        tmp.flush()

        with pytest.raises(TypeError):
            MockAgent.from_config_file(tmp.name)


def test_status_to_controller_success():
    """
    Test that successful POST request to controller is properly handled
    and logged.
    """
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


def test_status_to_controller_error():
    """
    Test that the HTTP failure of POST request to controller is properly
    handled and logged.
    """
    output = [
        (
            urllib2.HTTPError(
                url='http://mock/api/status/',
                code=500,
                msg='Internal Server Error',
                hdrs=None,
                fp=None,
            ),
            (
                'POST request to controller failed due to error: '
                'HTTP Error 500: Internal Server Error'
            ),
        ),
        (
            urllib2.URLError('Connection refused'),
            (
                'POST request to controller failed due to error: '
                '<urlopen error Connection refused>'
            )
        ),
    ]

    for error, msg in output:
        def mock_urlopen(request, timeout=5):
            raise error

        with tempfile.NamedTemporaryFile() as tmp:
            agent = MockAgent(port=12345)
            agent.setup_logging(tmp.name)
            agent.collect_server_metadata()

            agent.controller_url = 'http://mock/api/status/'

            with mock.patch('urllib2.urlopen', mock_urlopen):
                agent.status_to_controller()

            tmp.seek(0)
            contents = tmp.read()

            assert msg in contents, (
                'Expected %s in logs, got:\n%s' % (msg, contents)
            )
