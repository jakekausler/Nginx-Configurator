"""Tests for the configuration parser module."""

import pytest
import yaml
from pathlib import Path
import tempfile
import os

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.config_parser import ConfigParser


class TestConfigParser:
    """Test suite for ConfigParser class."""
    
    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'defaults': {
                    'enabled': True,
                    'ws': False,
                    'route': '/'
                },
                'sites': {
                    'test.example.com': {
                        'upstreams': [
                            {'target': '127.0.0.1:8080'}
                        ]
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)
        
        yield temp_path
        
        # Cleanup
        if temp_path.exists():
            temp_path.unlink()
    
    @pytest.fixture
    def fixture_config(self):
        """Return path to the test fixture configuration."""
        return Path(__file__).parent / 'fixtures' / 'test-config.yaml'
    
    def test_load_valid_config(self, temp_config_file):
        """Test loading a valid configuration file."""
        parser = ConfigParser(temp_config_file)
        
        assert 'test.example.com' in parser.sites
        assert parser.sites['test.example.com']['enabled'] is True
        assert len(parser.sites['test.example.com']['upstreams']) == 1
        assert parser.sites['test.example.com']['upstreams'][0]['target'] == '127.0.0.1:8080'
    
    def test_load_fixture_config(self, fixture_config):
        """Test loading the fixture configuration file."""
        parser = ConfigParser(fixture_config)
        
        # Check that all sites are loaded
        expected_sites = [
            'app.example.com',
            'static.example.com',
            'api.example.com',
            'chat.example.com',
            'custom.example.com',
            'disabled.example.com'
        ]
        
        for site in expected_sites:
            assert site in parser.sites
    
    def test_apply_defaults(self, fixture_config):
        """Test that defaults are properly applied."""
        parser = ConfigParser(fixture_config)
        
        # Check app.example.com has defaults applied
        app_site = parser.sites['app.example.com']
        assert app_site['enabled'] is True
        assert app_site['upstreams'][0]['route'] == '/'
        assert app_site['upstreams'][0]['ws'] is False
        assert app_site['upstreams'][0]['proxy_buffering'] == 'off'
    
    def test_websocket_configuration(self, fixture_config):
        """Test WebSocket configuration parsing."""
        parser = ConfigParser(fixture_config)
        
        # Check chat.example.com has WebSocket enabled
        chat_site = parser.sites['chat.example.com']
        assert chat_site['upstreams'][0]['ws'] is True
    
    def test_custom_headers(self, fixture_config):
        """Test custom headers parsing."""
        parser = ConfigParser(fixture_config)
        
        # Check custom.example.com has headers
        custom_site = parser.sites['custom.example.com']
        assert 'headers' in custom_site['upstreams'][0]
        assert custom_site['upstreams'][0]['headers']['X-Custom-Header'] == 'value'
        assert custom_site['upstreams'][0]['headers']['X-Another-Header'] == 'another-value'
    
    def test_disabled_site(self, fixture_config):
        """Test disabled site configuration."""
        parser = ConfigParser(fixture_config)
        
        # Check disabled.example.com is marked as disabled
        disabled_site = parser.sites['disabled.example.com']
        assert disabled_site['enabled'] is False
    
    def test_static_site(self, fixture_config):
        """Test static site with root directory."""
        parser = ConfigParser(fixture_config)
        
        # Check static.example.com has root but no ports
        static_site = parser.sites['static.example.com']
        assert static_site['root'] == '/var/www/static.example.com/html'
        assert 'upstreams' not in static_site
    
    def test_multiple_routes(self, fixture_config):
        """Test site with multiple routes."""
        parser = ConfigParser(fixture_config)
        
        # Check api.example.com has multiple routes
        api_site = parser.sites['api.example.com']
        assert len(api_site['upstreams']) == 2
        assert api_site['upstreams'][0]['route'] == '/api/'
        assert api_site['upstreams'][0]['target'] == '192.168.2.148:8746'
        assert api_site['upstreams'][1]['route'] == '/'
        assert api_site['upstreams'][1]['target'] == '192.168.2.148:8745'
    
    def test_get_site(self, fixture_config):
        """Test getting a specific site configuration."""
        parser = ConfigParser(fixture_config)
        
        site = parser.get_site('app.example.com')
        assert site is not None
        assert site['upstreams'][0]['target'] == '192.168.2.4:6767'
        
        # Test non-existent site
        site = parser.get_site('nonexistent.example.com')
        assert site is None
    
    def test_get_enabled_sites(self, fixture_config):
        """Test getting only enabled sites."""
        parser = ConfigParser(fixture_config)
        
        enabled_sites = parser.get_enabled_sites()
        
        # disabled.example.com should not be in enabled sites
        assert 'disabled.example.com' not in enabled_sites
        assert 'app.example.com' in enabled_sites
        assert 'static.example.com' in enabled_sites
    
    def test_empty_config(self):
        """Test handling of empty configuration file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('')
            temp_path = Path(f.name)
        
        try:
            parser = ConfigParser(temp_path)
            assert parser.sites == {}
            assert parser.defaults == ConfigParser.DEFAULT_CONFIG
        finally:
            temp_path.unlink()
    
    def test_missing_config_file(self):
        """Test handling of missing configuration file."""
        non_existent = Path('/tmp/non_existent_config.yaml')
        
        with pytest.raises(FileNotFoundError):
            ConfigParser(non_existent)
    
    def test_invalid_yaml(self):
        """Test handling of invalid YAML syntax."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('invalid: yaml: syntax: here')
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(yaml.YAMLError):
                ConfigParser(temp_path)
        finally:
            temp_path.unlink()
    
    def test_validate_config(self, fixture_config):
        """Test configuration validation."""
        parser = ConfigParser(fixture_config)
        
        errors = parser.validate_config()
        assert len(errors) == 0  # Fixture config should be valid
    
    def test_validate_invalid_domain(self):
        """Test validation with invalid domain name."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'sites': {
                    'invalid domain with spaces': {
                        'upstreams': [{'target': '127.0.0.1:8080'}]
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)
        
        try:
            parser = ConfigParser(temp_path)
            errors = parser.validate_config()
            assert len(errors) > 0
            assert any('Invalid domain name' in error for error in errors)
        finally:
            temp_path.unlink()
    
    def test_validate_missing_port(self):
        """Test validation with missing port field."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'sites': {
                    'test.example.com': {
                        'upstreams': [
                            {'route': '/'}  # Missing 'target' field
                        ]
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)
        
        try:
            parser = ConfigParser(temp_path)
            errors = parser.validate_config()
            assert len(errors) > 0
            assert any("missing 'target' field" in error for error in errors)
        finally:
            temp_path.unlink()
    
    def test_validate_invalid_port_format(self):
        """Test validation with invalid port format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'sites': {
                    'test.example.com': {
                        'upstreams': [
                            {'target': '8080'}  # Missing IP address
                        ]
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)
        
        try:
            parser = ConfigParser(temp_path)
            errors = parser.validate_config()
            assert len(errors) > 0
            assert any('invalid target format' in error for error in errors)
        finally:
            temp_path.unlink()
    
    def test_validate_no_config(self):
        """Test validation with site having neither ports nor root."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'sites': {
                    'test.example.com': {
                        'enabled': True
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)
        
        try:
            parser = ConfigParser(temp_path)
            errors = parser.validate_config()
            assert len(errors) > 0
            assert any("must have either 'upstreams' or 'root'" in error for error in errors)
        finally:
            temp_path.unlink()
    
    def test_custom_defaults(self):
        """Test custom default values override system defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            config = {
                'defaults': {
                    'enabled': False,
                    'ws': True,
                    'route': '/custom/',
                    'proxy_buffering': 'on'
                },
                'sites': {
                    'test.example.com': {
                        'upstreams': [{'target': '127.0.0.1:8080'}]
                    }
                }
            }
            yaml.dump(config, f)
            temp_path = Path(f.name)
        
        try:
            parser = ConfigParser(temp_path)
            
            # Check that custom defaults are applied
            site = parser.sites['test.example.com']
            assert site['enabled'] is False
            assert site['upstreams'][0]['ws'] is True
            assert site['upstreams'][0]['route'] == '/custom/'
            assert site['upstreams'][0]['proxy_buffering'] == 'on'
        finally:
            temp_path.unlink()


if __name__ == '__main__':
    # Run tests with pytest
    pytest.main([__file__, '-v'])