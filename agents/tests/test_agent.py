import tempfile

import mock

from agents.smtp import smtp


def test_to_controller_success():
    def mock_urlopen(request, timeout=5):
        class MockResponse(object):
            def getcode(self):
                return 201
        return MockResponse()

    with tempfile.NamedTemporaryFile() as tmp:
        agent = smtp.SMTPAgent(log_path=tmp.name)
        agent.controller_url = 'mock/api/status/'

        with mock.patch('urllib2.urlopen', mock_urlopen):
            agent.status_to_controller()

        tmp.seek(0)
        contents = tmp.read()

        assert 'POST request status: 201' in contents, (
            'POST request test failed'
        )
