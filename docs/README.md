# Nginx Sites Configuration Manager

A simplified YAML-based configuration management system for nginx sites that replaces manual configuration file management with a single source of truth.

## Features

- **Single YAML Configuration**: Manage all nginx sites from one `sites-config.yaml` file
- **Automatic SSL Integration**: Seamless Let's Encrypt certificate management via certbot
- **WebSocket Support**: Built-in WebSocket proxy configuration
- **Smart Defaults**: Sensible defaults with easy customization
- **Backup & Restore**: Automatic backups before changes with easy rollback
- **Clean Generation**: Complete site cleanup and regeneration for consistency
- **Migration Tool**: Import existing nginx configurations to YAML format

## Quick Start

### 1. Migrate Existing Configurations

```bash
sudo ./nginx-sites migrate > sites-config.yaml
```

This scans your `/etc/nginx/sites-available` directory and creates a YAML configuration file with all your existing sites.

### 2. Review and Edit Configuration

```bash
nano sites-config.yaml
```

The generated YAML will include all your current sites. Review and adjust as needed.

### 3. Generate Nginx Configurations

```bash
# Preview changes first
sudo ./nginx-sites generate --dry-run

# Apply changes
sudo ./nginx-sites generate
```

This will:
- Create a backup of existing configurations
- Remove old site configurations (preserving 'default')
- Generate fresh configurations from YAML
- Create symlinks for enabled sites
- Validate the nginx configuration

### 4. Validate and Test

```bash
# Check configuration
sudo ./nginx-sites validate

# View system status
sudo ./nginx-sites status

# Test your sites
curl -I https://yourdomain.com
```

## Commands Reference

### Core Commands

#### Generate Configurations
```bash
sudo ./nginx-sites generate [OPTIONS]

Options:
  --dry-run      Show what would be generated without making changes
  --no-backup    Skip creating backup before generation
  --force        Skip validation and force generation
```

#### Migrate Existing Setup
```bash
sudo ./nginx-sites migrate [OPTIONS]

Options:
  -o, --output FILE    Output file (default: sites-config.yaml)
  --dry-run           Show migration preview without writing file
```

#### Validate Configuration
```bash
sudo ./nginx-sites validate [OPTIONS]

Options:
  --check-permissions    Check system permissions
```

#### System Status
```bash
sudo ./nginx-sites status [OPTIONS]

Options:
  --show-ssl    Show SSL certificate information
```

### SSL Certificate Management

```bash
# Request certificate for a domain
sudo ./nginx-sites ssl domain.com [--email admin@domain.com]

# Test certificate request
sudo ./nginx-sites ssl domain.com --dry-run
```

### Backup Management

```bash
# Create manual backup
sudo ./nginx-sites backup create [--description "reason"]

# List available backups
./nginx-sites backup list

# Restore from backup
sudo ./nginx-sites backup restore backup-name.tar.gz [--force]
```

## Configuration Format

### Basic Structure

```yaml
defaults:
  enabled: true              # Enable sites by default
  ws: false                  # WebSocket support disabled by default
  route: "/"                 # Default route
  proxy_buffering: "off"     # Default proxy buffering setting

sites:
  domain.example.com:
    # Site-specific configuration
```

### Configuration Examples

#### Simple Proxy Site
```yaml
sites:
  app.example.com:
    upstreams:
      - target: 127.0.0.1:3000
```

#### Multiple Routes
```yaml
sites:
  api.example.com:
    upstreams:
      - target: 127.0.0.1:3000
        route: /api/
      - target: 127.0.0.1:8080
        route: /
```

#### WebSocket Support
```yaml
sites:
  chat.example.com:
    upstreams:
      - target: 127.0.0.1:8080
        ws: true  # Enables WebSocket support with /ws/ route
```

#### Static Site
```yaml
sites:
  blog.example.com:
    root: /var/www/blog.example.com/html
```

#### Mixed Static and Proxy
```yaml
sites:
  hybrid.example.com:
    root: /var/www/hybrid.example.com/html
    upstreams:
      - target: 127.0.0.1:3000
        route: /api/
```

#### Custom Headers
```yaml
sites:
  service.example.com:
    upstreams:
      - target: 127.0.0.1:8080
        headers:
          X-Custom-Header: "custom-value"
          X-Forward-Proto: "https"
```

#### Disabled Site
```yaml
sites:
  old-service.example.com:
    enabled: false
    upstreams:
      - target: 127.0.0.1:9000
```

### Field Reference

| Field | Type | Description | Default |
|-------|------|-------------|---------|
| `enabled` | boolean | Whether to generate config and enable site | `true` |
| `root` | string | Document root directory for static files | - |
| `upstreams` | array | List of proxy upstream configurations | - |
| `upstreams[].target` | string | Target upstream (IP:port or IP:port/path) | - |
| `upstreams[].route` | string | URL path for this upstream | `"/"` |
| `upstreams[].ws` | boolean | Enable WebSocket support | `false` |
| `upstreams[].enabled` | boolean | Whether this upstream is active | `true` |
| `upstreams[].headers` | object | Custom headers for this location | `{}` |
| `proxy_buffering` | string | Proxy buffering setting | `"off"` |

## Workflow Examples

### Adding a New Site

1. **Add to YAML configuration:**
   ```yaml
   sites:
     newsite.example.com:
       upstreams:
         - target: 192.168.1.100:8080
   ```

2. **Generate configuration:**
   ```bash
   sudo ./nginx-sites generate
   ```

3. **Request SSL certificate:**
   ```bash
   sudo ./nginx-sites ssl newsite.example.com --email admin@example.com
   ```

4. **Regenerate with SSL:**
   ```bash
   sudo ./nginx-sites generate
   ```

### Updating an Existing Site

1. **Edit YAML configuration**
2. **Preview changes:**
   ```bash
   sudo ./nginx-sites generate --dry-run
   ```
3. **Apply changes:**
   ```bash
   sudo ./nginx-sites generate
   ```

### Temporarily Disabling a Site

```yaml
sites:
  maintenance.example.com:
    enabled: false  # Add this line
    upstreams:
      - target: 127.0.0.1:8080
```

Then regenerate: `sudo ./nginx-sites generate`

## Advanced Features

### WebSocket Configuration

When `ws: true` is set on an upstream, the system automatically:
- Adds the WebSocket upgrade map directive
- Creates a `/ws/` location block with WebSocket headers
- Maintains the original location for regular HTTP traffic

### Backup System

- Automatic backups are created before each `generate` command
- Backups include both `sites-available` and `sites-enabled` directories
- Restore functionality validates and reloads nginx automatically
- Old backups can be cleaned up with retention policies

### Validation

The system validates:
- YAML syntax and structure
- Nginx configuration syntax
- System permissions
- SSL certificate existence

## Troubleshooting

### Common Issues

**1. Permission Denied**
```bash
# Ensure you're using sudo for system operations
sudo ./nginx-sites generate
```

**2. Configuration Validation Fails**
```bash
# Check the specific error
sudo ./nginx-sites validate

# View nginx error details
sudo nginx -t
```

**3. SSL Certificate Fails**
- Ensure domain points to your server
- Check firewall allows ports 80 and 443
- Verify DNS propagation: `dig yourdomain.com`

**4. Site Not Accessible**
```bash
# Check if site is enabled
ls -la /etc/nginx/sites-enabled/

# Check nginx error logs
sudo tail -f /var/log/nginx/error.log

# Ensure backend service is running
sudo systemctl status your-service
```

**5. Backup Restore Issues**
```bash
# List available backups
./nginx-sites backup list

# Restore specific backup
sudo ./nginx-sites backup restore backup-name.tar.gz --force
```

### Getting Help

```bash
# General help
./nginx-sites --help

# Command-specific help
./nginx-sites generate --help
./nginx-sites backup --help
```

## Safety Features

- **Automatic Backups**: Every `generate` command creates a timestamped backup
- **Dry Run Mode**: Preview all changes before applying
- **Configuration Validation**: Prevents invalid nginx configurations
- **Rollback Capability**: Quick restore from any backup
- **Permission Checking**: Validates required system permissions

## Files and Directories

```
/storage/programs/nginx-configuator/
├── nginx-sites              # Main executable
├── sites-config.yaml        # Your configuration file
├── templates/               # Nginx configuration templates
├── backups/                 # Automatic backups
├── lib/                     # Python modules
└── docs/                    # Documentation
```

## Requirements

- Python 3.6+
- nginx
- certbot (for SSL certificates)
- sudo privileges for system operations

## Installation

1. **Clone or download the project**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Make executable:**
   ```bash
   chmod +x nginx-sites
   ```
4. **Optional - Create system symlink:**
   ```bash
   sudo ln -s /storage/programs/nginx-configuator/nginx-sites /usr/local/bin/nginx-sites
   ```

## Contributing

This is a specialized tool for managing nginx configurations. When making changes:

1. Update tests in the `tests/` directory
2. Update documentation
3. Test thoroughly with `--dry-run` before applying changes
4. Follow the existing code style and patterns

## License

This project is designed for personal/internal use. Adjust licensing as needed for your organization.