#!/usr/bin/env python3
"""
Nginx configuration validation and reload utilities.

Provides validation of nginx configurations and safe reload operations.
"""

import subprocess
from pathlib import Path
from typing import Tuple, Optional, List
import logging
import re

logger = logging.getLogger(__name__)


class NginxValidator:
    """Validate and manage nginx configurations."""
    
    def __init__(self, nginx_binary: str = 'nginx', systemctl_binary: str = 'systemctl'):
        """
        Initialize validator with command paths.
        
        Args:
            nginx_binary: Path to nginx binary (default: 'nginx')
            systemctl_binary: Path to systemctl binary (default: 'systemctl')
        """
        self.nginx_binary = nginx_binary
        self.systemctl_binary = systemctl_binary
    
    def validate_config(self) -> Tuple[bool, str]:
        """
        Validate nginx configuration using nginx -t.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            result = subprocess.run(
                [self.nginx_binary, '-t'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # nginx -t writes to stderr even on success
            output = result.stderr if result.stderr else result.stdout
            
            if result.returncode == 0:
                logger.info("Nginx configuration is valid")
                return True, output
            else:
                logger.error(f"Nginx configuration is invalid: {output}")
                return False, output
                
        except subprocess.TimeoutExpired:
            msg = "Nginx validation timed out after 10 seconds"
            logger.error(msg)
            return False, msg
        except FileNotFoundError:
            msg = f"Nginx binary not found: {self.nginx_binary}"
            logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Failed to validate nginx configuration: {str(e)}"
            logger.error(msg)
            return False, msg
    
    def reload_nginx(self) -> Tuple[bool, str]:
        """
        Reload nginx service using systemctl.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        # Always validate before reload
        valid, validation_msg = self.validate_config()
        if not valid:
            return False, f"Configuration validation failed: {validation_msg}"
        
        try:
            result = subprocess.run(
                [self.systemctl_binary, 'reload', 'nginx'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info("Nginx reloaded successfully")
                return True, "Nginx reloaded successfully"
            else:
                output = result.stderr if result.stderr else result.stdout
                logger.error(f"Failed to reload nginx: {output}")
                return False, output
                
        except subprocess.TimeoutExpired:
            msg = "Nginx reload timed out after 10 seconds"
            logger.error(msg)
            return False, msg
        except FileNotFoundError:
            msg = f"systemctl binary not found: {self.systemctl_binary}"
            logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Failed to reload nginx: {str(e)}"
            logger.error(msg)
            return False, msg
    
    def check_syntax(self, config_file: Path) -> Tuple[bool, str]:
        """
        Check syntax of a specific configuration file.
        
        Args:
            config_file: Path to configuration file to check
            
        Returns:
            Tuple of (valid: bool, message: str)
        """
        if not config_file.exists():
            return False, f"Configuration file not found: {config_file}"
        
        try:
            # Use nginx -t with -c to test specific config
            result = subprocess.run(
                [self.nginx_binary, '-t', '-c', str(config_file)],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stderr if result.stderr else result.stdout
            
            if result.returncode == 0:
                return True, "Configuration syntax is valid"
            else:
                return False, output
                
        except Exception as e:
            return False, f"Syntax check failed: {str(e)}"
    
    def get_nginx_version(self) -> Optional[str]:
        """
        Get nginx version information.
        
        Returns:
            Version string or None if unable to determine
        """
        try:
            result = subprocess.run(
                [self.nginx_binary, '-v'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # nginx writes version to stderr
            output = result.stderr if result.stderr else result.stdout
            
            # Extract version from output
            match = re.search(r'nginx/(\S+)', output)
            if match:
                return match.group(1)
            
            return output.strip()
            
        except Exception as e:
            logger.error(f"Failed to get nginx version: {e}")
            return None
    
    def get_loaded_modules(self) -> List[str]:
        """
        Get list of loaded nginx modules.
        
        Returns:
            List of module names
        """
        try:
            result = subprocess.run(
                [self.nginx_binary, '-V'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # nginx writes build info to stderr
            output = result.stderr if result.stderr else result.stdout
            
            modules = []
            for line in output.split('\n'):
                if '--with-' in line or '--add-module=' in line:
                    # Extract module names
                    for item in line.split():
                        if item.startswith('--with-'):
                            module = item.replace('--with-', '').replace('_module', '')
                            modules.append(module)
                        elif item.startswith('--add-module='):
                            module = Path(item.replace('--add-module=', '')).name
                            modules.append(module)
            
            return modules
            
        except Exception as e:
            logger.error(f"Failed to get loaded modules: {e}")
            return []
    
    def test_site_config(self, site_name: str) -> Tuple[bool, str]:
        """
        Test a specific site configuration.
        
        Args:
            site_name: Name of the site to test
            
        Returns:
            Tuple of (valid: bool, message: str)
        """
        site_config = Path(f'/etc/nginx/sites-available/{site_name}')
        
        if not site_config.exists():
            return False, f"Site configuration not found: {site_name}"
        
        # Read the config to check for common issues
        try:
            content = site_config.read_text()
            
            # Check for common issues
            issues = []
            
            # Check for duplicate server_name directives
            server_names = re.findall(r'server_name\s+([^;]+);', content)
            if len(server_names) > 1:
                # Check if they're in different server blocks
                server_blocks = content.count('server {')
                if len(server_names) > server_blocks:
                    issues.append("Multiple server_name directives in same server block")
            
            # Check for missing semicolons (common syntax error)
            lines = content.split('\n')
            for i, line in enumerate(lines, 1):
                line = line.strip()
                if line and not line.startswith('#'):
                    # Check if line should end with semicolon
                    if any(line.startswith(d) for d in ['server_name', 'listen', 'root', 
                                                          'index', 'proxy_pass', 'return',
                                                          'proxy_set_header', 'add_header']):
                        if not line.endswith(';') and not line.endswith('{'):
                            issues.append(f"Line {i}: Missing semicolon")
            
            # Check for unclosed braces
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces != close_braces:
                issues.append(f"Unmatched braces: {open_braces} open, {close_braces} close")
            
            if issues:
                return False, "Configuration issues found:\n" + "\n".join(issues)
            
            # If no obvious issues, do actual nginx test
            return self.validate_config()
            
        except Exception as e:
            return False, f"Failed to test site config: {str(e)}"
    
    def check_port_conflicts(self) -> List[str]:
        """
        Check for port binding conflicts in nginx configurations.
        
        Returns:
            List of conflict messages (empty if no conflicts)
        """
        conflicts = []
        port_map = {}  # port -> list of sites
        
        sites_dir = Path('/etc/nginx/sites-enabled')
        if not sites_dir.exists():
            return conflicts
        
        for site_file in sites_dir.iterdir():
            if site_file.is_file() or site_file.is_symlink():
                try:
                    content = site_file.read_text()
                    
                    # Find all listen directives
                    listen_matches = re.findall(r'listen\s+(\S+)(?:\s+(\S+))?;', content)
                    
                    for match in listen_matches:
                        port_spec = match[0]
                        
                        # Extract port number
                        if ':' in port_spec:
                            port = port_spec.split(':')[-1]
                        else:
                            port = port_spec
                        
                        # Handle default ports
                        if match[1] == 'ssl':
                            port = port if port.isdigit() else '443'
                        elif not port.isdigit():
                            port = '80'
                        
                        if port not in port_map:
                            port_map[port] = []
                        port_map[port].append(site_file.name)
                        
                except Exception as e:
                    logger.error(f"Failed to check {site_file}: {e}")
        
        # Check for conflicts (multiple sites on same port without server_name)
        for port, sites in port_map.items():
            if len(sites) > 1:
                # This is not necessarily a conflict if they have different server_names
                # For now, just log as potential conflict
                logger.warning(f"Multiple sites on port {port}: {', '.join(sites)}")
        
        return conflicts
    
    def get_error_log_recent(self, lines: int = 20) -> List[str]:
        """
        Get recent lines from nginx error log.
        
        Args:
            lines: Number of recent lines to return
            
        Returns:
            List of log lines
        """
        error_log = Path('/var/log/nginx/error.log')
        
        if not error_log.exists():
            return []
        
        try:
            result = subprocess.run(
                ['tail', '-n', str(lines), str(error_log)],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
            
        except Exception as e:
            logger.error(f"Failed to read error log: {e}")
        
        return []