# -*- coding: utf-8 -*-

from agents.smtp.smtp import SMTPAgent


def test_banner_check():
    agent = SMTPAgent()
    result = agent.check_banner()
    assert 'status' in result
    assert result['status'] in ('ok', 'no banner', 'error')


if __name__ == '__main__':
    test_banner_check()
    print('✔ SMTP banner test passed.')
