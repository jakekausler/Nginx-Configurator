import pytest
from lib.migrator import NginxMigrator
from pathlib import Path


def test_parse_simple_proxy(tmp_path):
    """Test parsing a simple proxy configuration"""
    # Create test nginx config
    config_file = tmp_path / "test.example.com"
    config_file.write_text("""
server {
    server_name test.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
    }
    
    listen 443 ssl;
}
""")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    assert config is not None
    assert config['upstreams'][0]['target'] == '127.0.0.1:8080'
    assert config['enabled'] is False  # Not in sites-enabled


def test_detect_websocket(tmp_path):
    """Test WebSocket detection"""
    config_file = tmp_path / "websocket.example.com"
    config_file.write_text("""
server {
    server_name websocket.example.com;
    
    location /ws/ {
        proxy_pass http://192.168.1.100:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
    
    location / {
        proxy_pass http://192.168.1.100:8080;
    }
    
    listen 443 ssl;
}
""")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    assert config is not None
    assert len(config['upstreams']) == 1  # Should merge /ws/ into main location
    assert config['upstreams'][0]['target'] == '192.168.1.100:8080'
    assert config['upstreams'][0]['ws'] is True


def test_extract_custom_root(tmp_path):
    """Test custom root extraction"""
    config_file = tmp_path / "static.example.com"
    config_file.write_text("""
server {
    root /var/www/custom/path;
    server_name static.example.com;
    
    listen 443 ssl;
}
""")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    assert config is not None
    assert config['root'] == '/var/www/custom/path'


def test_ignore_default_root(tmp_path):
    """Test that default root is ignored"""
    config_file = tmp_path / "default-root.example.com"
    config_file.write_text("""
server {
    root /var/www/jakekausler.com/html;
    server_name default-root.example.com;
    
    location / {
        proxy_pass http://127.0.0.1:8080;
    }
    
    listen 443 ssl;
}
""")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    assert config is not None
    assert 'root' not in config  # Should be filtered out


def test_multiple_locations(tmp_path):
    """Test multiple location blocks"""
    config_file = tmp_path / "multi.example.com"
    config_file.write_text("""
server {
    server_name multi.example.com;
    
    location /api/ {
        proxy_pass http://192.168.1.100:8081;
    }
    
    location / {
        proxy_pass http://192.168.1.100:8080;
    }
    
    listen 443 ssl;
}
""")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    assert config is not None
    assert len(config['upstreams']) == 2
    
    # Should have routes in the right order
    routes = {upstream['route'] if 'route' in upstream else '/': upstream['target'] for upstream in config['upstreams']}
    assert routes['/api/'] == '192.168.1.100:8081'
    assert routes['/'] == '192.168.1.100:8080'


def test_extract_server_blocks():
    """Test server block extraction"""
    content = """
# Comment
server {
    listen 80;
    server_name example.com;
}

server {
    listen 443 ssl;
    server_name example.com;
    
    location / {
        proxy_pass http://localhost:8080;
    }
}

# Another comment
"""
    
    migrator = NginxMigrator(Path('/tmp'))
    blocks = migrator._extract_server_blocks(content)
    
    assert len(blocks) == 2
    assert 'listen 80' in blocks[0]
    assert 'listen 443' in blocks[1]
    assert 'proxy_pass' in blocks[1]


def test_find_https_block():
    """Test finding HTTPS server block"""
    blocks = [
        """server {
    listen 80;
    server_name example.com;
}""",
        """server {
    listen 443 ssl;
    server_name example.com;
    location / {
        proxy_pass http://localhost:8080;
    }
}"""
    ]
    
    migrator = NginxMigrator(Path('/tmp'))
    https_block = migrator._find_https_block(blocks)
    
    assert https_block is not None
    assert 'listen 443' in https_block
    assert 'proxy_pass' in https_block


def test_migrate_all_integration(tmp_path):
    """Test complete migration of multiple sites"""
    # Create multiple test configs
    sites = {
        'simple.example.com': """
server {
    server_name simple.example.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
    }
    listen 443 ssl;
}""",
        'websocket.example.com': """
server {
    server_name websocket.example.com;
    location /ws/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Upgrade $http_upgrade;
    }
    location / {
        proxy_pass http://127.0.0.1:9000;
    }
    listen 443 ssl;
}""",
        'static.example.com': """
server {
    root /var/www/static;
    server_name static.example.com;
    listen 443 ssl;
}"""
    }
    
    for domain, config in sites.items():
        (tmp_path / domain).write_text(config)
    
    migrator = NginxMigrator(tmp_path)
    result = migrator.migrate_all()
    
    assert 'defaults' in result
    assert 'sites' in result
    assert len(result['sites']) == 3
    
    # Check simple proxy
    simple = result['sites']['simple.example.com']
    assert simple['upstreams'][0]['target'] == '127.0.0.1:8080'
    
    # Check websocket
    websocket = result['sites']['websocket.example.com']
    assert websocket['upstreams'][0]['ws'] is True
    
    # Check static site
    static = result['sites']['static.example.com']
    assert static['root'] == '/var/www/static'


def test_skip_non_https_configs(tmp_path):
    """Test that configs without HTTPS blocks are skipped"""
    config_file = tmp_path / "http-only.example.com"
    config_file.write_text("""
server {
    listen 80;
    server_name http-only.example.com;
    location / {
        proxy_pass http://127.0.0.1:8080;
    }
}
""")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    assert config is None


def test_handle_invalid_files(tmp_path):
    """Test handling of invalid or unreadable files"""
    # Create a file that can't be parsed as nginx config
    config_file = tmp_path / "invalid.example.com"
    config_file.write_text("This is not a valid nginx config")
    
    migrator = NginxMigrator(tmp_path)
    config = migrator._parse_nginx_config(config_file)
    
    # Should return None for configs without valid server blocks
    assert config is None