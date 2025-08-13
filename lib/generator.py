"""
Nginx configuration generator using Jinja2 templates.

This module generates nginx server configurations from parsed YAML configurations
using Jinja2 templates for consistent and maintainable output.
"""

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from pathlib import Path
from typing import Dict, List, Optional
import re


class NginxGenerator:
    """Generate nginx configurations from parsed config."""
    
    def __init__(self, template_dir: Path):
        """
        Initialize the nginx configuration generator.
        
        Args:
            template_dir: Path to directory containing Jinja2 templates
            
        Raises:
            FileNotFoundError: If template directory doesn't exist
        """
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")
        
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def generate_site(self, domain: str, config: Dict) -> str:
        """
        Generate nginx config for a single site.
        
        Args:
            domain: The domain name for this site
            config: Site configuration dictionary with defaults applied
            
        Returns:
            Generated nginx configuration as a string
            
        Raises:
            TemplateNotFound: If required template files are missing
        """
        try:
            template = self.env.get_template('server-block.j2')
        except TemplateNotFound as e:
            raise TemplateNotFound(f"Required template not found: {e}")
        
        # Prepare template context
        context = self._prepare_context(domain, config)
        
        # Render template
        return template.render(**context)
    
    def _prepare_context(self, domain: str, config: Dict) -> Dict:
        """
        Prepare context for template rendering.
        
        Args:
            domain: The domain name
            config: Site configuration
            
        Returns:
            Dictionary containing context for template rendering
        """
        # Process the configuration for template rendering
        processed_config = self._process_config(config)
        
        context = {
            'domain': domain,
            'include_www': True,  # Could be configurable in the future
            'site': processed_config,
            'ssl_configured': self._check_ssl_exists(domain),
            'locations': self._build_locations(config)
        }
        return context
    
    def _process_config(self, config: Dict) -> Dict:
        """
        Process configuration for template rendering.
        
        Args:
            config: Raw site configuration
            
        Returns:
            Processed configuration with computed values
        """
        processed = config.copy()
        
        # Determine if WebSocket map is needed
        processed['websocket_needed'] = self._needs_websocket_map(config)
        
        return processed
    
    def _needs_websocket_map(self, config: Dict) -> bool:
        """
        Check if WebSocket map directive is needed.
        
        Args:
            config: Site configuration
            
        Returns:
            True if any upstream has WebSocket support enabled
        """
        if 'upstreams' not in config:
            return False
        
        for upstream_config in config['upstreams']:
            if upstream_config.get('ws', False) and upstream_config.get('enabled', True):
                return True
        
        return False
    
    def _build_locations(self, config: Dict) -> List[Dict]:
        """
        Build location blocks from upstream configurations.
        
        Args:
            config: Site configuration
            
        Returns:
            List of location block configurations
        """
        locations = []
        
        # Handle static site (root directive only)
        if config.get('root') and not config.get('upstreams'):
            # Static site - no location blocks needed
            return locations
        
        if not config.get('upstreams'):
            return locations
        
        for upstream_config in config['upstreams']:
            if not upstream_config.get('enabled', True):
                continue
            
            # Standard location for the route
            location = {
                'route': upstream_config.get('route', '/'),
                'target': upstream_config['target'],
                'websocket': False,
                'headers': upstream_config.get('headers', {})
            }
            locations.append(location)
            
            # Add WebSocket location if needed
            if upstream_config.get('ws', False):
                # For WebSocket support, we need both regular and WebSocket locations
                # The WebSocket location typically handles /ws/ path
                ws_location = {
                    'route': self._get_websocket_route(upstream_config.get('route', '/')),
                    'target': upstream_config['target'],
                    'websocket': True,
                    'headers': upstream_config.get('headers', {})
                }
                
                # Only add if it's different from the main route
                if ws_location['route'] != location['route']:
                    locations.append(ws_location)
                else:
                    # If the main route is for WebSocket, mark it as such
                    location['websocket'] = True
        
        return locations
    
    def _get_websocket_route(self, base_route: str) -> str:
        """
        Get the WebSocket route for a given base route.
        
        Args:
            base_route: The base route path
            
        Returns:
            WebSocket route path
        """
        # If the route is already root, WebSocket connections often use /ws/
        if base_route == '/':
            return '/ws/'
        
        # For other routes, append ws/ 
        # e.g., /api/ becomes /api/ws/
        if base_route.endswith('/'):
            return f"{base_route}ws/"
        else:
            return f"{base_route}/ws/"
    
    def _check_ssl_exists(self, domain: str) -> bool:
        """
        Check if SSL certificates exist for domain.
        
        Args:
            domain: Domain name to check
            
        Returns:
            True if SSL certificates exist, False otherwise (or if permission denied)
        """
        cert_path = Path(f'/etc/letsencrypt/live/{domain}/fullchain.pem')
        try:
            return cert_path.exists()
        except PermissionError:
            # If we can't check due to permissions, assume no SSL for dry-run purposes
            # This allows dry-run to work without sudo privileges
            return False
    
    def generate_all_sites(self, sites_config: Dict[str, Dict]) -> Dict[str, str]:
        """
        Generate nginx configurations for all sites.
        
        Args:
            sites_config: Dictionary of site configurations
            
        Returns:
            Dictionary mapping domain names to their nginx configurations
        """
        results = {}
        
        for domain, config in sites_config.items():
            if not config.get('enabled', True):
                continue
            
            try:
                results[domain] = self.generate_site(domain, config)
            except Exception as e:
                # Log error but continue with other sites
                raise RuntimeError(f"Failed to generate configuration for {domain}: {e}")
        
        return results
    
    def validate_template_syntax(self) -> List[str]:
        """
        Validate that all required templates exist and have valid syntax.
        
        Returns:
            List of validation errors (empty if all templates are valid)
        """
        errors = []
        required_templates = ['server-block.j2', 'location-block.j2', 'ssl-section.j2']
        
        for template_name in required_templates:
            try:
                template = self.env.get_template(template_name)
                # Try to render with minimal context to check syntax
                template.render(
                    domain='test.example.com',
                    site={'upstreams': [], 'websocket_needed': False},
                    ssl_configured=False,
                    locations=[],
                    include_www=True
                )
            except TemplateNotFound:
                errors.append(f"Required template not found: {template_name}")
            except Exception as e:
                errors.append(f"Template syntax error in {template_name}: {e}")
        
        return errors