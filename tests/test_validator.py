#!/usr/bin/env python3
"""
Unit tests for nginx validation functionality.
"""

import pytest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.validator import NginxValidator


class TestNginxValidator:
    """Test cases for NginxValidator class."""
    
    @pytest.fixture
    def validator(self):
        """Create a NginxValidator instance."""
        return NginxValidator()
    
    @pytest.fixture
    def custom_validator(self):
        """Create a NginxValidator with custom binary paths."""
        return NginxValidator(
            nginx_binary='/usr/sbin/nginx',
            systemctl_binary='/usr/bin/systemctl'
        )
    
    def test_init_default_binaries(self, validator):
        """Test validator initializes with default binary paths."""
        assert validator.nginx_binary == 'nginx'
        assert validator.systemctl_binary == 'systemctl'
    
    def test_init_custom_binaries(self, custom_validator):
        """Test validator initializes with custom binary paths."""
        assert custom_validator.nginx_binary == '/usr/sbin/nginx'
        assert custom_validator.systemctl_binary == '/usr/bin/systemctl'
    
    @patch('lib.validator.subprocess.run')
    def test_validate_config_success(self, mock_run, validator):
        """Test successful configuration validation."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr='nginx: configuration file /etc/nginx/nginx.conf test is successful',
            stdout=''
        )
        
        valid, message = validator.validate_config()
        
        assert valid is True
        assert 'test is successful' in message
        mock_run.assert_called_once_with(
            ['nginx', '-t'],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('lib.validator.subprocess.run')
    def test_validate_config_failure(self, mock_run, validator):
        """Test failed configuration validation."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr='nginx: [emerg] unexpected "}" in /etc/nginx/sites-enabled/test.com:5',
            stdout=''
        )
        
        valid, message = validator.validate_config()
        
        assert valid is False
        assert 'unexpected "}"' in message
    
    @patch('lib.validator.subprocess.run')
    def test_validate_config_timeout(self, mock_run, validator):
        """Test validation timeout handling."""
        mock_run.side_effect = subprocess.TimeoutExpired('nginx -t', 10)
        
        valid, message = validator.validate_config()
        
        assert valid is False
        assert 'timed out' in message.lower()
    
    @patch('lib.validator.subprocess.run')
    def test_validate_config_nginx_not_found(self, mock_run, validator):
        """Test handling when nginx binary is not found."""
        mock_run.side_effect = FileNotFoundError()
        
        valid, message = validator.validate_config()
        
        assert valid is False
        assert 'not found' in message.lower()
    
    @patch('lib.validator.subprocess.run')
    def test_reload_nginx_success(self, mock_run, validator):
        """Test successful nginx reload."""
        # Mock both validation and reload calls
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr='test is successful', stdout=''),  # validation
            MagicMock(returncode=0, stderr='', stdout='')  # reload
        ]
        
        success, message = validator.reload_nginx()
        
        assert success is True
        assert 'successfully' in message.lower()
        assert mock_run.call_count == 2
        
        # Check both calls
        calls = mock_run.call_args_list
        assert calls[0] == call(['nginx', '-t'], capture_output=True, text=True, timeout=10)
        assert calls[1] == call(['systemctl', 'reload', 'nginx'], capture_output=True, text=True, timeout=10)
    
    @patch('lib.validator.subprocess.run')
    def test_reload_nginx_validation_fails(self, mock_run, validator):
        """Test reload aborted when validation fails."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr='nginx: [emerg] invalid configuration',
            stdout=''
        )
        
        success, message = validator.reload_nginx()
        
        assert success is False
        assert 'validation failed' in message.lower()
        # Should only call validation, not reload
        mock_run.assert_called_once()
    
    @patch('lib.validator.subprocess.run')
    def test_reload_nginx_reload_fails(self, mock_run, validator):
        """Test handling when reload command fails."""
        mock_run.side_effect = [
            MagicMock(returncode=0, stderr='test is successful', stdout=''),  # validation succeeds
            MagicMock(returncode=1, stderr='Failed to reload nginx.service', stdout='')  # reload fails
        ]
        
        success, message = validator.reload_nginx()
        
        assert success is False
        assert 'Failed to reload' in message
    
    @patch('lib.validator.subprocess.run')
    def test_check_syntax_file_not_found(self, mock_run, validator):
        """Test syntax check with non-existent file."""
        config_file = Path('/tmp/nonexistent.conf')
        
        valid, message = validator.check_syntax(config_file)
        
        assert valid is False
        assert 'not found' in message
        mock_run.assert_not_called()
    
    @patch('lib.validator.subprocess.run')
    def test_check_syntax_valid(self, mock_run, validator, tmp_path):
        """Test syntax check with valid configuration."""
        config_file = tmp_path / 'test.conf'
        config_file.write_text('# test config')
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr='test is successful',
            stdout=''
        )
        
        valid, message = validator.check_syntax(config_file)
        
        assert valid is True
        assert 'valid' in message.lower()
        mock_run.assert_called_once_with(
            ['nginx', '-t', '-c', str(config_file)],
            capture_output=True,
            text=True,
            timeout=10
        )
    
    @patch('lib.validator.subprocess.run')
    def test_get_nginx_version(self, mock_run, validator):
        """Test getting nginx version."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr='nginx version: nginx/1.18.0 (Ubuntu)',
            stdout=''
        )
        
        version = validator.get_nginx_version()
        
        assert version == '1.18.0'
        mock_run.assert_called_once_with(
            ['nginx', '-v'],
            capture_output=True,
            text=True,
            timeout=5
        )
    
    @patch('lib.validator.subprocess.run')
    def test_get_nginx_version_error(self, mock_run, validator):
        """Test version retrieval error handling."""
        mock_run.side_effect = Exception('Command failed')
        
        version = validator.get_nginx_version()
        
        assert version is None
    
    @patch('lib.validator.subprocess.run')
    def test_get_loaded_modules(self, mock_run, validator):
        """Test getting loaded nginx modules."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stderr='''nginx version: nginx/1.18.0
configure arguments: --with-http_ssl_module --with-http_v2_module --with-http_realip_module
--add-module=/build/nginx/modules/ngx_http_geoip_module''',
            stdout=''
        )
        
        modules = validator.get_loaded_modules()
        
        assert 'http_ssl' in modules
        assert 'http_v2' in modules
        assert 'http_realip' in modules
        assert 'ngx_http_geoip_module' in modules
    
    @patch('lib.validator.subprocess.run')
    def test_get_loaded_modules_error(self, mock_run, validator):
        """Test module retrieval error handling."""
        mock_run.side_effect = Exception('Command failed')
        
        modules = validator.get_loaded_modules()
        
        assert modules == []
    
    def test_test_site_config_not_found(self, validator):
        """Test site config test with non-existent site."""
        with patch('lib.validator.Path.exists', return_value=False):
            valid, message = validator.test_site_config('nonexistent.com')
            
            assert valid is False
            assert 'not found' in message
    
    @patch('lib.validator.Path.read_text')
    @patch('lib.validator.Path.exists')
    def test_test_site_config_duplicate_server_name(self, mock_exists, mock_read, validator):
        """Test detection of duplicate server_name directives."""
        mock_exists.return_value = True
        mock_read.return_value = '''
        server {
            server_name test.com;
            server_name www.test.com;
            listen 80;
        }
        '''
        
        valid, message = validator.test_site_config('test.com')
        
        assert valid is False
        assert 'Multiple server_name' in message
    
    @patch('lib.validator.Path.read_text')
    @patch('lib.validator.Path.exists')
    def test_test_site_config_missing_semicolon(self, mock_exists, mock_read, validator):
        """Test detection of missing semicolons."""
        mock_exists.return_value = True
        mock_read.return_value = '''
        server {
            server_name test.com
            listen 80;
        }
        '''
        
        valid, message = validator.test_site_config('test.com')
        
        assert valid is False
        assert 'Missing semicolon' in message
    
    @patch('lib.validator.Path.read_text')
    @patch('lib.validator.Path.exists')
    def test_test_site_config_unmatched_braces(self, mock_exists, mock_read, validator):
        """Test detection of unmatched braces."""
        mock_exists.return_value = True
        mock_read.return_value = '''
        server {
            server_name test.com;
            location / {
                proxy_pass http://localhost:8080;
        }
        '''
        
        valid, message = validator.test_site_config('test.com')
        
        assert valid is False
        assert 'Unmatched braces' in message
    
    @patch('lib.validator.NginxValidator.validate_config')
    @patch('lib.validator.Path.read_text')
    @patch('lib.validator.Path.exists')
    def test_test_site_config_valid(self, mock_exists, mock_read, mock_validate, validator):
        """Test site config with valid configuration."""
        mock_exists.return_value = True
        mock_read.return_value = '''
        server {
            server_name test.com;
            listen 80;
            
            location / {
                proxy_pass http://localhost:8080;
            }
        }
        '''
        mock_validate.return_value = (True, 'Configuration is valid')
        
        valid, message = validator.test_site_config('test.com')
        
        assert valid is True
        mock_validate.assert_called_once()
    
    @patch('lib.validator.Path.iterdir')
    @patch('lib.validator.Path.exists')
    def test_check_port_conflicts(self, mock_exists, mock_iterdir, validator):
        """Test port conflict detection."""
        mock_exists.return_value = True
        
        # Create mock site files
        site1 = MagicMock()
        site1.name = 'site1.com'
        site1.is_file.return_value = True
        site1.read_text.return_value = 'listen 80;'
        
        site2 = MagicMock()
        site2.name = 'site2.com'
        site2.is_file.return_value = True
        site2.read_text.return_value = 'listen 80;'
        
        mock_iterdir.return_value = [site1, site2]
        
        conflicts = validator.check_port_conflicts()
        
        # Should detect potential conflict (logged as warning)
        # but not return as error since they might have different server_names
        assert conflicts == []
    
    @patch('lib.validator.subprocess.run')
    def test_get_error_log_recent(self, mock_run, validator):
        """Test getting recent error log lines."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='2024/01/15 10:00:00 [error] Test error 1\n2024/01/15 10:00:01 [error] Test error 2',
            stderr=''
        )
        
        with patch('lib.validator.Path.exists', return_value=True):
            lines = validator.get_error_log_recent(lines=2)
            
            assert len(lines) == 2
            assert 'Test error 1' in lines[0]
            assert 'Test error 2' in lines[1]
    
    def test_get_error_log_recent_no_log(self, validator):
        """Test error log retrieval when log doesn't exist."""
        with patch('lib.validator.Path.exists', return_value=False):
            lines = validator.get_error_log_recent()
            
            assert lines == []
    
    @patch('lib.validator.subprocess.run')
    def test_get_error_log_recent_error(self, mock_run, validator):
        """Test error log retrieval error handling."""
        mock_run.side_effect = Exception('Failed to read log')
        
        with patch('lib.validator.Path.exists', return_value=True):
            lines = validator.get_error_log_recent()
            
            assert lines == []