import re
from pathlib import Path
from typing import Dict, List, Optional


class NginxMigrator:
    """Migrate existing nginx configs to YAML format"""
    
    def __init__(self, sites_available_dir: Path):
        self.sites_dir = sites_available_dir
        self.sites = {}
    
    def migrate_all(self) -> Dict:
        """Migrate all sites to configuration dict"""
        for config_file in self.sites_dir.glob('*'):
            if config_file.name == 'default':
                continue
            
            domain = config_file.name
            config = self._parse_nginx_config(config_file)
            if config:
                self.sites[domain] = config
        
        return {
            'defaults': self._extract_defaults(),
            'sites': self.sites
        }
    
    def _parse_nginx_config(self, file_path: Path) -> Optional[Dict]:
        """Parse a single nginx configuration file"""
        try:
            content = file_path.read_text()
        except (IOError, OSError, UnicodeDecodeError):
            return None
        
        # Extract server blocks
        server_blocks = self._extract_server_blocks(content)
        if not server_blocks:
            return None
        
        # Find HTTPS server block (primary)
        https_block = self._find_https_block(server_blocks)
        if not https_block:
            return None
        
        # Parse configuration
        config = {
            'enabled': self._is_enabled(file_path.name),
            'upstreams': self._extract_proxy_configs(https_block),
            'root': self._extract_root(https_block)
        }
        
        # Clean up empty values
        config = {k: v for k, v in config.items() if v is not None and v != []}
        
        return config
    
    def _extract_server_blocks(self, content: str) -> List[str]:
        """Extract server blocks from nginx config"""
        # Regex to match server blocks with balanced braces
        blocks = []
        lines = content.split('\n')
        current_block = []
        brace_count = 0
        in_server_block = False
        
        for line in lines:
            stripped = line.strip()
            
            if stripped.startswith('server {'):
                in_server_block = True
                current_block = [line]
                brace_count = 1
            elif in_server_block:
                current_block.append(line)
                brace_count += stripped.count('{')
                brace_count -= stripped.count('}')
                
                if brace_count == 0:
                    blocks.append('\n'.join(current_block))
                    current_block = []
                    in_server_block = False
        
        return blocks
    
    def _find_https_block(self, blocks: List[str]) -> Optional[str]:
        """Find the HTTPS server block"""
        for block in blocks:
            if 'listen 443' in block or 'listen [::]:443' in block:
                return block
        return None
    
    def _extract_proxy_configs(self, block: str) -> List[Dict]:
        """Extract proxy configurations from server block"""
        configs = []
        websocket_routes = {}  # Track websocket routes by target
        
        # Find all location blocks
        location_pattern = r'location\s+([^\s{]+)\s*{([^}]*)}'
        locations = re.findall(location_pattern, block, re.DOTALL)
        
        # First pass: identify all websocket routes
        for route, location_content in locations:
            proxy_match = re.search(r'proxy_pass\s+http://([^;]+);', location_content)
            if not proxy_match:
                continue
            
            # Extract the upstream target (could include path, e.g. "192.168.1.1:8080/api/")
            upstream_target = proxy_match.group(1)
            has_websocket = 'proxy_set_header Upgrade' in location_content
            
            if has_websocket and route == '/ws/':
                websocket_routes[upstream_target] = True
        
        # Second pass: build configurations
        for route, location_content in locations:
            # Extract proxy_pass
            proxy_match = re.search(r'proxy_pass\s+http://([^;]+);', location_content)
            if not proxy_match:
                continue
            
            # Extract the upstream target (could include path, e.g. "192.168.1.1:8080/api/")
            upstream_target = proxy_match.group(1)
            has_websocket = 'proxy_set_header Upgrade' in location_content
            
            # Skip /ws/ routes if there's a corresponding / route for the same target
            if route == '/ws/' and upstream_target in websocket_routes:
                continue
            
            # Build upstream config
            upstream_config = {'target': upstream_target}
            
            if route != '/':
                upstream_config['route'] = route
            
            # Mark as websocket if this is the main route and there's a /ws/ route for same target
            # OR if this route itself has websocket headers
            if (route == '/' and upstream_target in websocket_routes) or (has_websocket and route == '/'):
                upstream_config['ws'] = True
            
            configs.append(upstream_config)
        
        return configs
    
    def _extract_root(self, block: str) -> Optional[str]:
        """Extract root directive if present"""
        match = re.search(r'root\s+([^;]+);', block)
        if match:
            root = match.group(1).strip()
            # Only return non-default roots
            if root != '/var/www/jakekausler.com/html':
                return root
        return None
    
    def _is_enabled(self, domain: str) -> bool:
        """Check if site is enabled"""
        enabled_path = Path(f'/etc/nginx/sites-enabled/{domain}')
        return enabled_path.exists()
    
    def _extract_defaults(self) -> Dict:
        """Extract common defaults from all configs"""
        # Analyze all configs to find common patterns
        return {
            'enabled': True,
            'ws': False,
            'route': '/',
            'proxy_buffering': 'off'
        }