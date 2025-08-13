"""
YAML configuration parser for nginx site configurations.

This module handles loading YAML configuration files and applying
default values to site configurations.
"""

import yaml
from typing import Dict, Any, List, Optional
from pathlib import Path
import copy


class ConfigParser:
    """Parse and validate sites configuration with defaults."""
    
    DEFAULT_CONFIG = {
        'enabled': True,
        'ws': False,
        'route': '/',
        'proxy_buffering': 'off'
    }
    
    def __init__(self, config_path: Path):
        """
        Initialize the configuration parser.
        
        Args:
            config_path: Path to the YAML configuration file
        
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the YAML file is invalid
        """
        self.config_path = config_path
        self.raw_config = self._load_yaml()
        self.defaults = self._parse_defaults()
        self.sites = self._parse_sites()
    
    def _load_yaml(self) -> Dict:
        """
        Load YAML configuration file.
        
        Returns:
            Dictionary containing the parsed YAML
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            yaml.YAMLError: If the YAML file is invalid
        """
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            try:
                config = yaml.safe_load(f)
                if config is None:
                    return {}
                return config
            except yaml.YAMLError as e:
                raise yaml.YAMLError(f"Invalid YAML in {self.config_path}: {e}")
    
    def _parse_defaults(self) -> Dict:
        """
        Merge user defaults with system defaults.
        
        Returns:
            Dictionary containing merged defaults
        """
        user_defaults = self.raw_config.get('defaults', {})
        return {**self.DEFAULT_CONFIG, **user_defaults}
    
    def _parse_sites(self) -> Dict:
        """
        Parse sites with defaults applied.
        
        Returns:
            Dictionary of site configurations with defaults applied
        """
        sites = {}
        for domain, config in self.raw_config.get('sites', {}).items():
            if config is None:
                config = {}
            sites[domain] = self._apply_defaults(config)
        return sites
    
    def _apply_defaults(self, site_config: Dict) -> Dict:
        """
        Apply defaults to site configuration.
        
        This method applies both site-level defaults and port-level defaults.
        
        Args:
            site_config: Raw site configuration from YAML
            
        Returns:
            Site configuration with all defaults applied
        """
        # Make a deep copy to avoid modifying the original
        config = copy.deepcopy(site_config) if site_config else {}
        
        # Apply site-level defaults
        if 'enabled' not in config:
            config['enabled'] = self.defaults['enabled']
        
        # Apply defaults to ports if they exist
        if 'ports' in config and isinstance(config['ports'], list):
            for port_config in config['ports']:
                # Apply port-level defaults
                if 'route' not in port_config:
                    port_config['route'] = self.defaults['route']
                
                if 'ws' not in port_config:
                    port_config['ws'] = self.defaults['ws']
                
                if 'enabled' not in port_config:
                    port_config['enabled'] = True
                
                if 'proxy_buffering' not in port_config:
                    port_config['proxy_buffering'] = self.defaults.get('proxy_buffering', 'off')
                
                # Ensure headers is a dict
                if 'headers' not in port_config:
                    port_config['headers'] = {}
                elif not isinstance(port_config['headers'], dict):
                    port_config['headers'] = {}
        
        # Handle root-only sites (static sites)
        if 'root' in config and 'ports' not in config:
            # Static site with no proxy configuration
            pass
        
        # Apply proxy_buffering default at site level if not specified
        if 'proxy_buffering' not in config and 'ports' in config:
            config['proxy_buffering'] = self.defaults.get('proxy_buffering', 'off')
        
        return config
    
    def get_site(self, domain: str) -> Optional[Dict]:
        """
        Get configuration for a specific site.
        
        Args:
            domain: The domain name to get configuration for
            
        Returns:
            Site configuration or None if site doesn't exist
        """
        return self.sites.get(domain)
    
    def get_enabled_sites(self) -> Dict[str, Dict]:
        """
        Get all enabled sites.
        
        Returns:
            Dictionary of enabled site configurations
        """
        return {
            domain: config 
            for domain, config in self.sites.items() 
            if config.get('enabled', True)
        }
    
    def validate_config(self) -> List[str]:
        """
        Validate the configuration for common issues.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        for domain, config in self.sites.items():
            # Check for valid domain format (basic check)
            if not domain or ' ' in domain:
                errors.append(f"Invalid domain name: '{domain}'")
            
            # Check ports configuration
            if 'ports' in config:
                if not isinstance(config['ports'], list):
                    errors.append(f"{domain}: 'ports' must be a list")
                else:
                    for i, port_config in enumerate(config['ports']):
                        if not isinstance(port_config, dict):
                            errors.append(f"{domain}: port config {i} must be a dictionary")
                            continue
                        
                        # Check for required 'port' field
                        if 'port' not in port_config:
                            errors.append(f"{domain}: port config {i} missing 'port' field")
                        else:
                            # Validate port format (basic check)
                            port = port_config['port']
                            if not isinstance(port, str) or ':' not in port:
                                errors.append(f"{domain}: invalid port format '{port}' (expected IP:PORT)")
            
            # Check root configuration
            if 'root' in config:
                if not isinstance(config['root'], str):
                    errors.append(f"{domain}: 'root' must be a string path")
            
            # Check that site has either 'ports' or 'root'
            if 'ports' not in config and 'root' not in config:
                errors.append(f"{domain}: site must have either 'ports' or 'root' configuration")
        
        return errors