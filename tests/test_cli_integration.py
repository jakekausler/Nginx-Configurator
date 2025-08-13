"""
Simple CLI integration tests using subprocess calls.

These tests verify the nginx-sites command-line interface by executing
the script as a subprocess, which is more realistic than importing it.
"""

import pytest
import subprocess
import tempfile
import yaml
from pathlib import Path


class TestCLIIntegration:
    """Test CLI functionality through subprocess calls."""
    
    @pytest.fixture
    def nginx_sites_script(self):
        """Path to the nginx-sites script."""
        return Path(__file__).parent.parent / "nginx-sites"
    
    @pytest.fixture
    def temp_config(self):
        """Create temporary configuration file for testing."""
        config_content = {
            'defaults': {
                'enabled': True,
                'ws': False,
                'route': '/',
                'proxy_buffering': 'off'
            },
            'sites': {
                'test.example.com': {
                    'upstreams': [
                        {'target': '127.0.0.1:8080'}
                    ]
                },
                'websocket.example.com': {
                    'upstreams': [
                        {'target': '127.0.0.1:8080', 'ws': True}
                    ]
                },
                'disabled.example.com': {
                    'enabled': False,
                    'upstreams': [
                        {'target': '127.0.0.1:9000'}
                    ]
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_content, f, default_flow_style=False)
            return f.name
    
    def test_help_command(self, nginx_sites_script):
        """Test that help command works."""
        result = subprocess.run(
            [str(nginx_sites_script), '--help'], 
            capture_output=True, 
            text=True
        )
        
        assert result.returncode == 0
        assert 'Nginx Sites Configuration Manager' in result.stdout
        assert 'generate' in result.stdout
    
    def test_generate_dry_run(self, nginx_sites_script, temp_config):
        """Test generate command with dry-run."""
        result = subprocess.run([
            str(nginx_sites_script), 
            '--config', temp_config,
            'generate', '--dry-run'
        ], capture_output=True, text=True)
        
        # Should work even without sudo since it's dry-run
        assert result.returncode == 0
        assert 'test.example.com' in result.stdout
        assert 'websocket.example.com' in result.stdout
        assert 'disabled.example.com' not in result.stdout
        assert 'Dry run complete' in result.stdout
    
    def test_validate_command(self, nginx_sites_script, temp_config):
        """Test validate command."""
        result = subprocess.run([
            str(nginx_sites_script),
            '--config', temp_config,
            'validate'
        ], capture_output=True, text=True)
        
        # Should validate YAML successfully (nginx validation may fail)
        # Return code 0 or 1 is acceptable depending on nginx availability
        assert result.returncode in [0, 1]
        assert 'YAML configuration is valid' in result.stdout or 'Error' in result.stderr
    
    def test_status_command(self, nginx_sites_script, temp_config):
        """Test status command."""
        result = subprocess.run([
            str(nginx_sites_script),
            '--config', temp_config,
            'status'
        ], capture_output=True, text=True)
        
        # Should run without error
        assert result.returncode == 0
        assert 'Configuration Status:' in result.stdout
    
    def test_migrate_dry_run(self, nginx_sites_script):
        """Test migrate command with dry-run."""
        result = subprocess.run([
            str(nginx_sites_script),
            'migrate', '--dry-run'
        ], capture_output=True, text=True)
        
        # Should complete without error even if no sites found
        assert result.returncode == 0
    
    def test_backup_list(self, nginx_sites_script):
        """Test backup list command."""
        result = subprocess.run([
            str(nginx_sites_script),
            'backup', 'list'
        ], capture_output=True, text=True)
        
        # Should run without error
        assert result.returncode == 0
        # May show no backups or list existing ones
        assert 'backup' in result.stdout.lower() or 'no backups' in result.stdout.lower()
    
    def test_invalid_command(self, nginx_sites_script):
        """Test invalid command handling."""
        result = subprocess.run([
            str(nginx_sites_script),
            'nonexistent-command'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert 'No such command' in result.stderr or 'Usage:' in result.stderr
    
    def test_verbose_flag(self, nginx_sites_script, temp_config):
        """Test verbose flag."""
        result = subprocess.run([
            str(nginx_sites_script),
            '--verbose',
            '--config', temp_config,
            'status'
        ], capture_output=True, text=True)
        
        # Should run successfully
        assert result.returncode == 0
    
    def test_missing_config_file(self, nginx_sites_script):
        """Test behavior with missing configuration file."""
        result = subprocess.run([
            str(nginx_sites_script),
            '--config', '/nonexistent/config.yaml',
            'generate', '--dry-run'
        ], capture_output=True, text=True)
        
        assert result.returncode == 2  # Click returns 2 for invalid options
        assert 'does not exist' in result.stderr


class TestCLIWorkflow:
    """Test complete CLI workflows."""
    
    def test_help_hierarchy(self):
        """Test that all main commands have help."""
        script = Path(__file__).parent.parent / "nginx-sites"
        
        # Test main help
        result = subprocess.run([str(script), '--help'], capture_output=True, text=True)
        assert result.returncode == 0
        
        # Test subcommand help
        commands_to_test = ['generate', 'migrate', 'validate', 'status']
        
        for command in commands_to_test:
            result = subprocess.run([str(script), command, '--help'], capture_output=True, text=True)
            # Should show help for each command
            assert result.returncode == 0
            assert '--help' in result.stdout
    
    def test_config_validation_workflow(self):
        """Test the configuration validation workflow."""
        script = Path(__file__).parent.parent / "nginx-sites"
        
        # Create invalid YAML
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            invalid_config = f.name
        
        # Should fail validation
        result = subprocess.run([
            str(script),
            '--config', invalid_config,
            'validate'
        ], capture_output=True, text=True)
        
        assert result.returncode == 1
        
        # Clean up
        Path(invalid_config).unlink()


if __name__ == '__main__':
    pytest.main([__file__])