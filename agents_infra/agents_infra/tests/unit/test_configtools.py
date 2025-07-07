import os
import unittest
from tempfile import NamedTemporaryFile

import ConfigParser

from ...utils.configtools import write_config_options


class TestWriteConfigOptions(unittest.TestCase):
    """
    Tests for the write_config_options utility function.
    """

    def setUp(self):
        """
        Create a temporary config file for each test.
        """
        self.temp_config_file = NamedTemporaryFile(mode='w', delete=False)
        self.config_path = self.temp_config_file.name
        self.temp_config_file.write('[server]\nenv = dev\nrole = db\n')
        self.temp_config_file.close()

    def tearDown(self):
        """
        Remove the temporary config file after each test.
        """
        os.remove(self.config_path)

    def _read_config(self):
        """
        Helper to read the current state of the temp config file.
        """
        config = ConfigParser.ConfigParser()
        config.read(self.config_path)
        return config

    def test_updates_existing_value(self):
        """
        Test that an existing value is correctly updated.
        """
        write_config_options(
            self.config_path,
            'server',
            {'env': 'production'}
        )
        config = self._read_config()
        self.assertEqual(config.get('server', 'env'), 'production')

    def test_adds_new_value(self):
        """
        Test that a new key-value pair is added.
        """
        write_config_options(
            self.config_path,
            'server',
            {'region': 'us-east'}
        )
        config = self._read_config()
        self.assertEqual(config.get('server', 'region'), 'us-east')
        self.assertEqual(config.get('server', 'role'), 'db')

    def test_removes_option_on_empty_string(self):
        """
        Test that providing an empty string removes an existing option.
        """
        self.assertTrue(self._read_config().has_option('server', 'role'))
        write_config_options(
            self.config_path,
            'server',
            {'role': ''}
        )
        self.assertFalse(self._read_config().has_option('server', 'role'))

    def test_removes_option_on_none_value(self):
        """
        Test that providing None removes an existing option.
        """
        self.assertTrue(self._read_config().has_option('server', 'role'))
        write_config_options(
            self.config_path,
            'server',
            {'role': None}
        )
        self.assertFalse(self._read_config().has_option('server', 'role'))

    def test_creates_section_if_not_exists(self):
        """
        Test that a new section is created if it does not exist.
        """
        write_config_options(
            self.config_path,
            'new_section',
            {'key': 'value'}
        )
        config = self._read_config()
        self.assertTrue(config.has_section('new_section'))
        self.assertEqual(config.get('new_section', 'key'), 'value')
