#!/usr/bin/env python3
"""
Basic CLI integration tests for nginx-sites CLI application.

Simple tests that verify the CLI is working without complex mocking.
"""

import subprocess
import tempfile
import yaml
from pathlib import Path
import pytest


class TestCLIBasic:
    """Basic CLI functionality tests."""
    
    def setup_method(self):
        """Setup test environment"""
        self.cli_path = Path(__file__).parent.parent / 'nginx-sites'
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_help_command(self):
        """Test that help command works"""
        result = subprocess.run(
            ['python3', str(self.cli_path), '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'Nginx Sites Configuration Manager' in result.stdout
        assert 'generate' in result.stdout
        assert 'migrate' in result.stdout
        assert 'ssl' in result.stdout
        assert 'backup' in result.stdout
        assert 'validate' in result.stdout
        assert 'status' in result.stdout
    
    def test_generate_help(self):
        """Test generate command help"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'generate', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'Generate nginx configurations from YAML' in result.stdout
        assert '--dry-run' in result.stdout
        assert '--no-backup' in result.stdout
        assert '--force' in result.stdout
    
    def test_migrate_help(self):
        """Test migrate command help"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'migrate', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'Import existing nginx configurations to YAML format' in result.stdout
        assert '--output' in result.stdout
        assert '--dry-run' in result.stdout
    
    def test_ssl_help(self):
        """Test SSL command help"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'ssl', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'Request SSL certificate for domain' in result.stdout
        assert '--email' in result.stdout
        assert '--dry-run' in result.stdout
    
    def test_backup_help(self):
        """Test backup command help"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'backup', '--help'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'Backup and restore nginx configurations' in result.stdout
        assert 'create' in result.stdout
        assert 'list' in result.stdout
        assert 'restore' in result.stdout
    
    def test_status_command(self):
        """Test status command (should work without sudo)"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'status'],
            capture_output=True,
            text=True
        )
        
        # Status command should run, even if it reports errors due to permissions
        assert 'Nginx Status:' in result.stdout
        assert 'Configuration Status:' in result.stdout
        assert 'Backup Status:' in result.stdout
    
    def test_validate_command(self):
        """Test validate command"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'validate'],
            capture_output=True,
            text=True
        )
        
        # Validate should run and try to validate nginx config
        assert 'Validating nginx configuration' in result.stdout
    
    def test_generate_missing_config(self):
        """Test generate with missing configuration file"""
        missing_config = self.temp_dir / 'missing.yaml'
        
        result = subprocess.run(
            ['python3', str(self.cli_path), '-c', str(missing_config), 'generate'],
            capture_output=True,
            text=True
        )
        
        # Click validates the path exists before the command runs
        assert result.returncode == 2
        assert 'does not exist' in result.stderr
    
    def test_generate_dry_run_with_config(self):
        """Test generate with dry-run and valid config"""
        # Create a simple test configuration
        test_config = {
            'defaults': {'enabled': True, 'ws': False, 'route': '/'},
            'sites': {
                'test.example.com': {
                    'upstreams': [{'target': '127.0.0.1:8080'}]
                }
            }
        }
        
        config_file = self.temp_dir / 'test.yaml'
        with open(config_file, 'w') as f:
            yaml.dump(test_config, f)
        
        result = subprocess.run(
            ['python3', str(self.cli_path), '-c', str(config_file), 'generate', '--dry-run'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'test.example.com' in result.stdout
        assert 'Dry run complete' in result.stdout
    
    def test_migrate_dry_run(self):
        """Test migrate command with dry-run (should work if /etc/nginx/sites-available exists)"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'migrate', '--dry-run'],
            capture_output=True,
            text=True
        )
        
        # Migration should either work or fail gracefully
        if result.returncode == 0:
            assert 'Migration preview:' in result.stdout
        else:
            # If it fails, it should be due to missing directory
            assert 'does not exist' in result.stdout
    
    def test_backup_list_empty(self):
        """Test backup list command with empty backup directory"""
        result = subprocess.run(
            ['python3', str(self.cli_path), 'backup', 'list'],
            capture_output=True,
            text=True
        )
        
        assert result.returncode == 0
        assert 'No backups found' in result.stdout or 'backup(s):' in result.stdout


if __name__ == '__main__':
    pytest.main([__file__, '-v'])