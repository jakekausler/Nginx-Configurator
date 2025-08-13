# YAML Configuration Schema

This document provides a complete reference for the `sites-config.yaml` configuration file structure used by the nginx-sites configuration manager.

## Schema Overview

```yaml
defaults:           # Global default values (optional)
  key: value        # Default settings applied to all sites

sites:             # Site definitions (required)
  domain.com:      # Domain name (key)
    # Site-specific configuration
```

## Top-Level Structure

### `defaults` (object, optional)

Global default values that apply to all sites unless overridden. All site-level properties can be set as defaults.

```yaml
defaults:
  enabled: true
  ws: false
  route: "/"
  proxy_buffering: "off"
```

### `sites` (object, required)

Dictionary mapping domain names to their configurations. Keys must be valid domain names.

```yaml
sites:
  example.com:        # Domain as key
    # Configuration for example.com
  api.example.com:    # Another domain
    # Configuration for api.example.com
```

## Site Configuration Properties

### Core Properties

#### `enabled` (boolean, optional, default: `true`)

Controls whether the site configuration is generated and enabled.

```yaml
sites:
  active-site.com:
    enabled: true     # Site will be generated and enabled
  
  disabled-site.com:
    enabled: false    # Site will be skipped during generation
```

**Generated Effect:**
- `true`: Configuration file created in `sites-available/` and symlinked in `sites-enabled/`
- `false`: Site completely skipped during generation

#### `root` (string, optional)

Document root directory for serving static files. Used for static websites or sites that serve files directly.

```yaml
sites:
  static-site.com:
    root: /var/www/static-site.com/html
  
  blog.com:
    root: /var/www/blog/public
    # Can be combined with upstreams for hybrid sites
    upstreams:
      - target: 127.0.0.1:3000
        route: /api/
```

**Generated Effect:**
```nginx
server {
    server_name static-site.com www.static-site.com;
    root /var/www/static-site.com/html;
    index index.html index.htm index.nginx-debian.html;
    # ...
}
```

#### `upstreams` (array, optional)

List of proxy upstream configurations. Each upstream defines a backend service to proxy requests to.

```yaml
sites:
  app.com:
    upstreams:
      - target: 127.0.0.1:8080
      - target: 192.168.1.100:3000
        route: /api/
```

**Note:** A site can have both `root` and `upstreams` for hybrid static/proxy configurations.

### Upstream Configuration

Each item in the `upstreams` array can have the following properties:

#### `target` (string, required)

The upstream server address in format `IP:PORT` or `IP:PORT/path`.

```yaml
upstreams:
  - target: 127.0.0.1:8080              # Local service
  - target: 192.168.1.100:3000          # Remote service
  - target: 192.168.1.100:8080/api/v1   # Service with path
```

**Generated Effect:**
```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
}
```

#### `route` (string, optional, default: `"/"`)

The URL path that should be proxied to this upstream.

```yaml
upstreams:
  - target: 127.0.0.1:8080
    route: /                    # Root path (default)
  
  - target: 127.0.0.1:3000
    route: /api/               # API endpoints
  
  - target: 127.0.0.1:9000
    route: /admin/             # Admin interface
```

**Generated Effect:**
```nginx
location / {
    proxy_pass http://127.0.0.1:8080;
}

location /api/ {
    proxy_pass http://127.0.0.1:3000;
}

location /admin/ {
    proxy_pass http://127.0.0.1:9000;
}
```

#### `ws` (boolean, optional, default: `false`)

Enables WebSocket support for this upstream.

```yaml
upstreams:
  - target: 127.0.0.1:8080
    ws: true                   # Enable WebSocket support
```

**Generated Effect:**
- Adds WebSocket upgrade map directive to the server block
- Creates additional `/ws/` location block with WebSocket headers
- If the route is `/`, creates both `/` and `/ws/` locations

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

server {
    # ...
    location / {
        proxy_pass http://127.0.0.1:8080;
    }
    
    location /ws/ {
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_pass http://127.0.0.1:8080;
    }
}
```

#### `enabled` (boolean, optional, default: `true`)

Controls whether this specific upstream is included in the configuration.

```yaml
upstreams:
  - target: 127.0.0.1:8080
    enabled: true              # This upstream will be included
  
  - target: 127.0.0.1:9000
    enabled: false             # This upstream will be skipped
```

#### `headers` (object, optional, default: `{}`)

Custom HTTP headers to add for this upstream location.

```yaml
upstreams:
  - target: 127.0.0.1:8080
    headers:
      X-Custom-Header: "custom-value"
      X-Real-IP: "$remote_addr"
      X-Forwarded-Proto: "https"
      Authorization: "Bearer token123"
```

**Generated Effect:**
```nginx
location / {
    proxy_set_header X-Custom-Header "custom-value";
    proxy_set_header X-Real-IP "$remote_addr";
    proxy_set_header X-Forwarded-Proto "https";
    proxy_set_header Authorization "Bearer token123";
    proxy_pass http://127.0.0.1:8080;
}
```

### Global Site Properties

#### `proxy_buffering` (string, optional, default: `"off"`)

Controls nginx proxy buffering for all upstreams in this site.

```yaml
sites:
  app.com:
    proxy_buffering: "on"      # Enable buffering
    upstreams:
      - target: 127.0.0.1:8080
  
  realtime.com:
    proxy_buffering: "off"     # Disable buffering (default)
    upstreams:
      - target: 127.0.0.1:8080
```

**Generated Effect:**
```nginx
server {
    # ...
    proxy_buffering on;  # or off
    # ...
}
```

## Complete Examples

### Simple Proxy Site
```yaml
sites:
  simple.example.com:
    upstreams:
      - target: 127.0.0.1:3000
```

### Multi-Service Application
```yaml
sites:
  app.example.com:
    upstreams:
      - target: 127.0.0.1:3000    # Frontend
        route: /
      - target: 127.0.0.1:8080    # API
        route: /api/
      - target: 127.0.0.1:9000    # Admin panel
        route: /admin/
```

### WebSocket Chat Application
```yaml
sites:
  chat.example.com:
    upstreams:
      - target: 127.0.0.1:8080
        ws: true
        headers:
          X-Real-IP: "$remote_addr"
```

### Static Site with API
```yaml
sites:
  website.example.com:
    root: /var/www/website/dist
    upstreams:
      - target: 127.0.0.1:3000
        route: /api/
      - target: 127.0.0.1:8080
        route: /webhooks/
```

### Development vs Production
```yaml
defaults:
  enabled: true
  proxy_buffering: "off"

sites:
  # Production services
  api.example.com:
    upstreams:
      - target: 192.168.1.100:8080
        headers:
          X-Environment: "production"
  
  # Development services (disabled in production)
  dev-api.example.com:
    enabled: false
    upstreams:
      - target: 127.0.0.1:8080
        headers:
          X-Environment: "development"
```

### Complex Multi-Domain Setup
```yaml
defaults:
  enabled: true
  ws: false
  proxy_buffering: "off"

sites:
  # Main website (static + API)
  example.com:
    root: /var/www/example.com/html
    upstreams:
      - target: 127.0.0.1:3000
        route: /api/v1/
        headers:
          X-API-Version: "1.0"
  
  # API subdomain
  api.example.com:
    upstreams:
      - target: 127.0.0.1:3000
        route: /v1/
      - target: 127.0.0.1:3001
        route: /v2/
        headers:
          X-API-Version: "2.0"
  
  # Real-time services
  ws.example.com:
    upstreams:
      - target: 127.0.0.1:8080
        ws: true
    proxy_buffering: "off"
  
  # Admin interface
  admin.example.com:
    upstreams:
      - target: 127.0.0.1:9000
        headers:
          X-Admin-Panel: "true"
  
  # Legacy service (disabled)
  old.example.com:
    enabled: false
    upstreams:
      - target: 192.168.1.200:8080
```

## Validation Rules

### Domain Names
- Must be valid DNS domain names
- Can include subdomains (e.g., `api.example.com`)
- Cannot contain spaces or special characters except hyphens and dots

### Target Addresses
- Must be valid IP address and port combination
- Format: `IP:PORT` or `IP:PORT/path`
- Examples: `127.0.0.1:8080`, `192.168.1.100:3000`, `10.0.0.1:8080/api/`

### Route Paths
- Must start with `/`
- Should end with `/` for directory-style routes
- Examples: `/`, `/api/`, `/admin/dashboard/`

### Boolean Values
- Use `true` or `false` (lowercase)
- Not `True`, `False`, `yes`, `no`, `1`, `0`

### Headers
- Header names should follow HTTP header conventions
- Header values can contain nginx variables (e.g., `$remote_addr`)
- Special characters in values should be quoted

## Default Inheritance

Properties are inherited in this order (later values override earlier):

1. Built-in system defaults
2. User-defined `defaults` section
3. Site-specific properties
4. Upstream-specific properties (for upstream-level settings)

### Built-in System Defaults
```yaml
enabled: true
ws: false
route: "/"
proxy_buffering: "off"
```

### Example of Inheritance
```yaml
defaults:
  enabled: true
  proxy_buffering: "on"
  ws: false

sites:
  app.example.com:
    # Inherits: enabled=true, proxy_buffering="on", ws=false
    upstreams:
      - target: 127.0.0.1:8080
        # Inherits all defaults
      - target: 127.0.0.1:8081
        ws: true              # Override: ws=true for this upstream only
        # Still inherits: enabled=true, proxy_buffering="on"
```

## SSL Certificate Integration

SSL certificates are automatically detected and configured:

- Certificates in `/etc/letsencrypt/live/DOMAIN/` are automatically included
- HTTPS server blocks are generated when certificates exist
- HTTP-to-HTTPS redirects are automatically created
- Both domain.com and www.domain.com are supported

## Generated nginx Structure

Each site generates:

1. **WebSocket map** (if any upstream has `ws: true`)
2. **Main server block** with HTTPS configuration (if SSL exists)
3. **HTTP redirect server block** (if SSL exists)
4. **Location blocks** for each upstream
5. **SSL configuration** (if certificates exist)

## Troubleshooting YAML

### Common YAML Syntax Issues

**Incorrect indentation:**
```yaml
# ❌ Wrong
sites:
example.com:
  upstreams:
  - target: 127.0.0.1:8080

# ✅ Correct
sites:
  example.com:
    upstreams:
      - target: 127.0.0.1:8080
```

**Missing colons:**
```yaml
# ❌ Wrong
sites:
  example.com
    upstreams:
      - target 127.0.0.1:8080

# ✅ Correct
sites:
  example.com:
    upstreams:
      - target: 127.0.0.1:8080
```

**Mixed data types:**
```yaml
# ❌ Wrong
enabled: "true"    # String instead of boolean

# ✅ Correct
enabled: true      # Boolean
```

### Validation Commands

```bash
# Validate YAML syntax and configuration
sudo ./nginx-sites validate

# Test configuration generation
sudo ./nginx-sites generate --dry-run

# Check specific YAML syntax (if you have Python)
python3 -c "import yaml; yaml.safe_load(open('sites-config.yaml'))"
```

## Schema Evolution

This schema is designed to be backward-compatible. Future versions may add:

- Additional upstream properties
- New global configuration options  
- Enhanced SSL configuration options
- Rate limiting and security features

Always check the documentation for your specific version of nginx-sites.