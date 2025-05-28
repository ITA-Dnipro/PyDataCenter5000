import os
import pytest
from mock import patch, MagicMock
from agents.web.web import WebAgent


@pytest.yield_fixture
def web_agent():
    """Fixture to create a WebAgent instance with required environment setup"""
    os.environ['PORT'] = '8000'
    yield WebAgent()

def test_to_dict_format(web_agent):
    """Test that to_dict returns a dictionary with correct keys and value types"""
    result = web_agent.to_dict()
    
    # Check all required keys are present
    required_keys = set(['os', 'hostname', 'ip', 'server_name', 'uptime', 'timestamp', 'healthy'])
    assert set(result.keys()) == required_keys
    
    # Check value types
    assert isinstance(result['os'], str)
    assert isinstance(result['hostname'], str)
    assert isinstance(result['ip'], (str, type(None)))
    assert result['server_name'] == 'web'
    assert isinstance(result['uptime'], (int, float))
    assert isinstance(result['timestamp'], str)
    assert isinstance(result['healthy'], bool)

def test_to_dict_timestamp_format(web_agent):
    """Test that timestamp in to_dict follows the correct format"""
    result = web_agent.to_dict()
    timestamp = result['timestamp']
    
    # Check timestamp format (YYYY-MM-DD HH:MM:SS)
    import re
    assert re.match(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$', timestamp) is not None

@patch('agents.web.web.WebAgent.service_healthy')
def test_to_dict_healthy_status(mock_healthy, web_agent):
    """Test that healthy status is correctly reflected in to_dict"""
    # Test when service is healthy
    mock_healthy.return_value = True
    result = web_agent.to_dict()
    assert result['healthy'] is True

    # Test when service is unhealthy
    mock_healthy.return_value = False
    result = web_agent.to_dict()
    assert result['healthy'] is False

def test_to_txt(web_agent):
    """Test that to_txt logs each key-value pair"""
    # Create a mock logger
    mock_logger = MagicMock()
    web_agent.logger = mock_logger
    
    web_agent.to_txt()
    
    # Get all logged messages
    logged_messages = [call[0][0] for call in mock_logger.info.call_args_list]
    
    # Check that each key-value pair from to_dict is logged
    dict_data = web_agent.to_dict()
    for key, value in dict_data.items():
        expected_message = '%s: %s' % (key, value)  
        assert expected_message in logged_messages
