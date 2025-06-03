# -*- coding: utf-8 -*-

from agents.smtp.smtp import SMTPAgent


def test_banner_check(host='127.0.0.1'):
    agent = SMTPAgent()
    result = agent.check_banner(host=host)

    assert 'status' in result
    assert result['status'] in ('ok', 'no banner', 'error')

    if result['status'] == 'ok':
        assert 'banner' in result
        assert result['banner'] is not None
    elif result['status'] == 'no banner':
        assert result.get('banner') is None
    elif result['status'] == 'error':
        assert 'error' in result

