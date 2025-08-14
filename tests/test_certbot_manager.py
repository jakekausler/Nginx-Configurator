import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import subprocess

from lib.certbot_manager import CertbotManager
from lib.permissions import InsufficientPermissionsError


class TestCertbotManager:
    """Test suite for CertbotManager class"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.certbot = CertbotManager(dry_run=True)
        self.certbot_prod = CertbotManager(dry_run=False)
    
    def test_check_certificate_exists(self):
        """Test certificate existence checking"""
        with patch('lib.certbot_manager.Path.exists') as mock_exists:
            mock_exists.return_value = True
            assert self.certbot.check_certificate_exists('example.com') is True
            
            mock_exists.return_value = False
            assert self.certbot.check_certificate_exists('example.com') is False
    
    @patch('lib.certbot_manager.subprocess.run')
    @patch('lib.certbot_manager.check_sudo_privileges')
    def test_request_certificate_success(self, mock_sudo, mock_run):
        """Test successful certificate request without www"""
        mock_sudo.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout='Certificate obtained')
        
        with patch.object(self.certbot_prod, 'check_certificate_exists', return_value=False):
            success, message = self.certbot_prod.request_certificate('example.com', 'admin@example.com')
            
            assert success is True
            assert 'Certificate obtained' in message
            
            # Verify command construction
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert 'certbot' in cmd
            assert '--nginx' in cmd
            assert '-d' in cmd
            assert 'example.com' in cmd
            assert 'www.example.com' not in cmd  # Should not include www by default
            assert '--email' in cmd
            assert 'admin@example.com' in cmd

    @patch('lib.certbot_manager.subprocess.run')
    @patch('lib.certbot_manager.check_sudo_privileges')
    def test_request_certificate_with_www(self, mock_sudo, mock_run):
        """Test successful certificate request with www"""
        mock_sudo.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout='Certificate obtained')
        
        with patch.object(self.certbot_prod, 'check_certificate_exists', return_value=False):
            success, message = self.certbot_prod.request_certificate('example.com', 'admin@example.com', include_www=True)
            
            assert success is True
            assert 'Certificate obtained' in message
            
            # Verify command construction
            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert 'certbot' in cmd
            assert '--nginx' in cmd
            assert '-d' in cmd
            assert 'example.com' in cmd
            assert 'www.example.com' in cmd  # Should include www when requested
            assert '--email' in cmd
            assert 'admin@example.com' in cmd
    
    @patch('lib.certbot_manager.subprocess.run')
    def test_request_certificate_dry_run(self, mock_run):
        """Test certificate request in dry-run mode"""
        mock_run.return_value = MagicMock(returncode=0, stdout='Dry run successful')
        
        with patch.object(self.certbot, 'check_certificate_exists', return_value=False):
            success, message = self.certbot.request_certificate('example.com')
            
            assert success is True
            
            # Verify dry-run flag is included
            cmd = mock_run.call_args[0][0]
            assert '--dry-run' in cmd
    
    def test_request_certificate_already_exists(self):
        """Test certificate request when certificate already exists"""
        with patch.object(self.certbot, 'check_certificate_exists', return_value=True):
            success, message = self.certbot.request_certificate('example.com')
            
            assert success is True
            assert 'already exists' in message
    
    @patch('lib.certbot_manager.check_sudo_privileges')
    def test_request_certificate_no_permissions(self, mock_sudo):
        """Test certificate request without sudo privileges"""
        mock_sudo.side_effect = InsufficientPermissionsError("No sudo")
        
        with patch.object(self.certbot_prod, 'check_certificate_exists', return_value=False):
            success, message = self.certbot_prod.request_certificate('example.com')
            
            assert success is False
            assert 'No sudo' in message
    
    @patch('lib.certbot_manager.subprocess.run')
    def test_get_certificate_info(self, mock_run):
        """Test getting certificate information"""
        mock_output = """
        Certificate Name: example.com
        Domains: example.com www.example.com
        Expiry Date: 2024-03-15 12:00:00
        Certificate Path: /etc/letsencrypt/live/example.com/cert.pem
        VALID: Expiry Date
        """
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        
        with patch.object(self.certbot, 'check_certificate_exists', return_value=True):
            info = self.certbot.get_certificate_info('example.com')
            
            assert info is not None
            assert 'expiry' in info
            assert 'cert_path' in info
            assert 'domains' in info
            assert info['valid'] is True
    
    def test_get_certificate_info_not_exists(self):
        """Test getting info for non-existent certificate"""
        with patch.object(self.certbot, 'check_certificate_exists', return_value=False):
            info = self.certbot.get_certificate_info('example.com')
            assert info is None
    
    @patch('lib.certbot_manager.subprocess.run')
    @patch('lib.certbot_manager.check_sudo_privileges')
    def test_renew_certificates(self, mock_sudo, mock_run):
        """Test certificate renewal"""
        mock_sudo.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout='Renewal successful')
        
        success, message = self.certbot_prod.renew_certificates()
        
        assert success is True
        assert 'Renewal successful' in message
        
        # Verify command
        cmd = mock_run.call_args[0][0]
        assert cmd == ['certbot', 'renew']
    
    @patch('lib.certbot_manager.subprocess.run')
    def test_renew_certificates_dry_run(self, mock_run):
        """Test certificate renewal in dry-run mode"""
        mock_run.return_value = MagicMock(returncode=0, stdout='Dry run successful')
        
        success, message = self.certbot.renew_certificates()
        
        assert success is True
        
        # Verify dry-run flag
        cmd = mock_run.call_args[0][0]
        assert '--dry-run' in cmd
    
    @patch('lib.certbot_manager.subprocess.run')
    def test_list_certificates(self, mock_run):
        """Test listing certificates"""
        mock_output = """- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Certificate Name: example.com
Domains: example.com www.example.com
Expiry Date: 2024-03-15 (VALID: 89 days)
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
Certificate Name: test.com
Domains: test.com
Expiry Date: 2024-01-15 (EXPIRED)
- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -"""
        mock_run.return_value = MagicMock(returncode=0, stdout=mock_output)
        
        certificates = self.certbot.list_certificates()
        
        assert len(certificates) == 2
        assert certificates[0]['name'] == 'example.com'
        assert certificates[0]['valid'] is True
        assert certificates[1]['name'] == 'test.com'
        assert certificates[1]['valid'] is False
    
    @patch('lib.certbot_manager.subprocess.run')
    @patch('lib.certbot_manager.check_sudo_privileges')
    def test_revoke_certificate(self, mock_sudo, mock_run):
        """Test certificate revocation"""
        mock_sudo.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout='Certificate revoked')
        
        with patch('lib.certbot_manager.Path.exists', return_value=True):
            success, message = self.certbot_prod.revoke_certificate('example.com', 'keycompromise')
            
            assert success is True
            assert 'Certificate revoked' in message
            
            # Verify command
            cmd = mock_run.call_args[0][0]
            assert 'certbot' in cmd
            assert 'revoke' in cmd
            assert '--reason' in cmd
            assert 'keycompromise' in cmd
    
    def test_revoke_certificate_not_found(self):
        """Test revoking non-existent certificate"""
        with patch('lib.certbot_manager.Path.exists', return_value=False):
            success, message = self.certbot.revoke_certificate('example.com')
            
            assert success is False
            assert 'not found' in message
    
    @patch('lib.certbot_manager.subprocess.run')
    @patch('lib.certbot_manager.check_sudo_privileges')
    def test_delete_certificate(self, mock_sudo, mock_run):
        """Test certificate deletion"""
        mock_sudo.return_value = None
        mock_run.return_value = MagicMock(returncode=0, stdout='Certificate deleted')
        
        success, message = self.certbot_prod.delete_certificate('example.com')
        
        assert success is True
        assert 'Certificate deleted' in message
        
        # Verify command
        cmd = mock_run.call_args[0][0]
        assert 'certbot' in cmd
        assert 'delete' in cmd
        assert '--cert-name' in cmd
        assert 'example.com' in cmd
    
    @patch('lib.certbot_manager.subprocess.run')
    def test_command_timeout(self, mock_run):
        """Test handling of command timeout"""
        mock_run.side_effect = subprocess.TimeoutExpired('certbot', 60)
        
        with patch.object(self.certbot, 'check_certificate_exists', return_value=False):
            success, message = self.certbot.request_certificate('example.com')
            
            assert success is False
            assert 'timed out' in message
    
    @patch('lib.certbot_manager.subprocess.run')
    def test_command_failure(self, mock_run):
        """Test handling of command failure"""
        mock_run.return_value = MagicMock(returncode=1, stderr='Error: Invalid domain')
        
        with patch.object(self.certbot, 'check_certificate_exists', return_value=False):
            success, message = self.certbot.request_certificate('invalid-domain')
            
            assert success is False
            assert 'Invalid domain' in message