# Migration Guide

This guide walks you through migrating from a traditional nginx configuration setup to the YAML-based nginx-sites configuration manager.

## Pre-Migration Checklist

Before starting the migration, ensure you have:

- [ ] Root/sudo access to the server
- [ ] Current nginx configurations working properly
- [ ] All SSL certificates functioning correctly
- [ ] A maintenance window (recommended, though downtime should be minimal)
- [ ] Access to DNS management (if certificate re-issuance is needed)

## Step 1: Backup Current Configuration

**Critical**: Always create a complete backup before making any changes.

```bash
# Create timestamped backup directory
sudo mkdir -p /root/nginx-backup-$(date +%Y%m%d-%H%M%S)
cd /root/nginx-backup-$(date +%Y%m%d-%H%M%S)

# Backup nginx configurations
sudo tar -czf nginx-sites-backup.tar.gz /etc/nginx/sites-available /etc/nginx/sites-enabled

# Backup main nginx config
sudo cp /etc/nginx/nginx.conf nginx.conf.backup

# Backup SSL certificates (optional but recommended)
sudo tar -czf letsencrypt-backup.tar.gz /etc/letsencrypt

# List what we backed up
ls -la
```

Store this backup location: `____________________`

## Step 2: Install nginx-sites

```bash
# Navigate to the installation directory
cd /storage/programs/nginx-configuator

# Install Python dependencies
pip install -r requirements.txt

# Make the script executable
chmod +x nginx-sites

# Test installation
./nginx-sites --help
```

## Step 3: Analyze Current Setup

Before migration, understand your current configuration:

```bash
# List current sites
ls -la /etc/nginx/sites-available/
ls -la /etc/nginx/sites-enabled/

# Count total sites
echo "Total sites-available: $(ls -1 /etc/nginx/sites-available/ | wc -l)"
echo "Total sites-enabled: $(ls -1 /etc/nginx/sites-enabled/ | wc -l)"

# Check for complex configurations
echo "Sites with WebSocket configurations:"
grep -l "proxy_set_header Upgrade" /etc/nginx/sites-available/* 2>/dev/null || echo "None found"

echo "Sites with custom headers:"
grep -l "proxy_set_header X-" /etc/nginx/sites-available/* 2>/dev/null || echo "None found"
```

Document any special configurations that might need manual review:
```
Special configurations found:
- ________________________________
- ________________________________
- ________________________________
```

## Step 4: Run Migration

```bash
# Change to nginx-sites directory
cd /storage/programs/nginx-configuator

# Run migration with preview
sudo ./nginx-sites migrate --dry-run

# If the preview looks good, create the configuration file
sudo ./nginx-sites migrate > sites-config.yaml

# Review the generated configuration
cat sites-config.yaml
```

### Migration Output Review

The migration will show something like:
```
Scanning /etc/nginx/sites-available for nginx configurations...
Found 12 sites
Migration complete! Configuration written to sites-config.yaml
  domain1.example.com: 1 upstream(s) - enabled
  domain2.example.com: 2 upstream(s) - enabled
  static.example.com: static site - enabled
  disabled.example.com: 1 upstream(s) - disabled
```

## Step 5: Review Generated Configuration

Carefully review the `sites-config.yaml` file:

### Common Things to Check:

1. **All sites are present**
   ```bash
   # Count sites in YAML
   grep -c "\.com:" sites-config.yaml
   ```

2. **Upstream targets are correct**
   - Look for `target:` entries
   - Verify IP addresses and ports match your services

3. **WebSocket sites have `ws: true`**
   - Find sites that should support WebSockets
   - Ensure they have `ws: true` in their upstream configuration

4. **Multiple routes are properly configured**
   - Sites with `/api/` routes should have multiple upstream entries
   - Check `route:` values are correct

5. **Static sites have `root:` directives**
   - Sites serving static files should have `root:` instead of `upstreams:`

6. **Disabled sites are marked correctly**
   - Sites that were not in `sites-enabled/` should have `enabled: false`

### Example Review Process:

```yaml
# ✅ Good - Simple proxy
podcast.example.com:
  upstreams:
    - target: 192.168.2.148:8585

# ✅ Good - WebSocket enabled
chat.example.com:
  upstreams:
    - target: 192.168.2.148:7492
      ws: true

# ✅ Good - Multiple routes
api.example.com:
  upstreams:
    - target: 192.168.2.148:8746
      route: /api/
    - target: 192.168.2.148:8745

# ✅ Good - Static site
blog.example.com:
  root: /var/www/blog.example.com/html

# ✅ Good - Disabled site
old-service.example.com:
  enabled: false
  upstreams:
    - target: 192.168.2.100:8000
```

## Step 6: Test Generation (Dry Run)

Test the configuration generation without making changes:

```bash
sudo ./nginx-sites generate --dry-run
```

### What to Look for in Dry Run Output:

1. **All expected sites appear**
2. **WebSocket sites show map directive**:
   ```nginx
   map $http_upgrade $connection_upgrade {
       default upgrade;
       ''      close;
   }
   ```
3. **WebSocket locations are created**:
   ```nginx
   location /ws/ {
       proxy_http_version 1.1;
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection $connection_upgrade;
       proxy_pass http://192.168.2.148:7492;
   }
   ```
4. **SSL certificates are detected** (if sites have SSL)
5. **Static sites have proper root directives**

If the dry run output looks incorrect, edit `sites-config.yaml` and run the dry run again.

## Step 7: Apply Migration

Once the dry run looks correct, apply the changes:

```bash
# Generate new configurations
sudo ./nginx-sites generate

# Verify nginx configuration is valid
sudo ./nginx-sites validate
```

Expected output:
```
Created backup: nginx_backup_20240813_143022_pre_generate.tar.gz
Removed 12 existing site configuration(s)
Removed 12 existing site symlink(s)
Generating configurations for 12 sites...
Generated: domain1.example.com
Enabled: domain1.example.com
[... more sites ...]
Successfully generated 12 configurations
Nginx reloaded successfully
```

## Step 8: Verify Migration

### 8.1 Check Nginx Status
```bash
# Check nginx is running
sudo systemctl status nginx

# Verify configuration
sudo nginx -t

# Check enabled sites
ls -la /etc/nginx/sites-enabled/
```

### 8.2 Test Each Site

Create a test checklist:

```bash
# Test HTTP redirect (should redirect to HTTPS)
curl -I http://domain1.example.com

# Test HTTPS response
curl -I https://domain1.example.com

# Test SSL certificate
openssl s_client -connect domain1.example.com:443 -servername domain1.example.com < /dev/null 2>/dev/null | grep -A 10 "Certificate chain"
```

**Testing Checklist:**
- [ ] `domain1.example.com` - HTTP/HTTPS working
- [ ] `domain2.example.com` - HTTP/HTTPS working  
- [ ] `websocket.example.com` - WebSocket connections work
- [ ] `static.example.com` - Static files served correctly
- [ ] `api.example.com` - API routes work correctly

### 8.3 Monitor Logs

```bash
# Watch nginx error logs
sudo tail -f /var/log/nginx/error.log

# Watch access logs
sudo tail -f /var/log/nginx/access.log
```

## Step 9: Post-Migration Tasks

### 9.1 Clean Up
```bash
# The old configurations are now in backups
# You can remove them from sites-available/sites-enabled if confident
# (but keep your manual backup from Step 1!)

# Optional: Remove old backup files after a few days
# ls -la /storage/programs/nginx-configuator/backups/
```

### 9.2 Update Documentation
- Update any deployment scripts to use `nginx-sites generate`
- Document the new workflow for your team
- Update monitoring/alerting for the new structure

### 9.3 Set Up Regular Maintenance
```bash
# Add to crontab for automatic backup cleanup (optional)
# 0 2 * * 0 /storage/programs/nginx-configuator/nginx-sites backup cleanup --keep 30
```

## Rollback Procedure

If something goes wrong, you can quickly rollback:

### Quick Rollback (using nginx-sites backups)
```bash
# List available backups
./nginx-sites backup list

# Restore the most recent backup
sudo ./nginx-sites backup restore backup-name.tar.gz --force
```

### Manual Rollback (using manual backup)
```bash
# Go to your backup directory from Step 1
cd /root/nginx-backup-YYYYMMDD-HHMMSS

# Restore configurations
sudo tar -xzf nginx-sites-backup.tar.gz -C /

# Reload nginx
sudo systemctl reload nginx
```

## Troubleshooting Common Issues

### Issue: SSL Certificates Not Found
**Symptoms**: Sites generate without SSL configuration
**Solution**:
```bash
# Check certificate paths
sudo ls -la /etc/letsencrypt/live/

# Manually request certificate if needed
sudo ./nginx-sites ssl domain.example.com --email admin@domain.example.com

# Regenerate configurations
sudo ./nginx-sites generate
```

### Issue: WebSocket Connections Fail
**Symptoms**: WebSocket connections timeout or fail to upgrade
**Solution**:
1. Verify `ws: true` is set in YAML configuration
2. Check the dry run output includes WebSocket headers
3. Ensure your application supports WebSocket connections

### Issue: Some Sites Missing After Migration
**Symptoms**: Sites that were working before don't appear in YAML
**Solution**:
1. Check if the site files were in `sites-available` but not linked in `sites-enabled`
2. Look for non-standard file names or configurations
3. Manually add missing sites to YAML configuration

### Issue: Custom Headers Lost
**Symptoms**: Applications that depend on custom headers stop working
**Solution**:
1. Add custom headers to YAML configuration:
   ```yaml
   sites:
     domain.example.com:
       upstreams:
         - target: 192.168.1.100:8080
           headers:
             X-Custom-Header: "value"
             X-Real-IP: "$remote_addr"
   ```
2. Regenerate configurations

### Issue: Multi-Domain Certificates
**Symptoms**: Certificate validation fails for www subdomains
**Solution**: The system automatically includes www subdomains in certificate requests. If you have custom multi-domain certificates, ensure all domains are covered.

## Advanced Migration Scenarios

### Scenario 1: Complex Location Blocks
If you have complex nginx location blocks that don't fit the standard pattern:

1. Note the special configurations
2. Consider if they can be simplified
3. If needed, manually edit generated configurations (understanding they'll be overwritten on next generate)
4. Consider extending the template system for permanent customizations

### Scenario 2: Multiple Server Blocks Per File
If your current setup has multiple server blocks in one file:

1. The migration will attempt to parse the HTTPS block
2. You may need to manually split configurations
3. Create separate YAML entries for each domain

### Scenario 3: Custom nginx Modules
If you use custom nginx modules or special directives:

1. These won't be migrated automatically
2. Consider adding them to the template system
3. Or maintain custom configurations separately

## Success Criteria

Your migration is successful when:

- [ ] All sites are accessible via HTTP and HTTPS
- [ ] SSL certificates are working correctly
- [ ] WebSocket connections function properly (if applicable)
- [ ] No errors in nginx error logs
- [ ] All API endpoints and routes work correctly
- [ ] Static files are served properly
- [ ] `nginx-sites generate --dry-run` shows expected output
- [ ] `nginx-sites validate` shows no errors

## Ongoing Usage

After successful migration, your workflow becomes:

1. **Edit** `sites-config.yaml` to make changes
2. **Preview** with `sudo ./nginx-sites generate --dry-run`
3. **Apply** with `sudo ./nginx-sites generate`
4. **Monitor** logs and functionality

For new sites:
1. Add to YAML configuration
2. Generate configurations
3. Request SSL certificate: `sudo ./nginx-sites ssl newdomain.com`
4. Regenerate to include SSL: `sudo ./nginx-sites generate`

## Getting Help

If you encounter issues during migration:

1. Check the dry run output carefully
2. Review nginx error logs: `sudo tail -f /var/log/nginx/error.log`
3. Validate your YAML syntax: `sudo ./nginx-sites validate`
4. Use the rollback procedure if needed
5. Compare generated configs with your original configurations

Remember: The manual backup from Step 1 is your safety net. Keep it until you're confident the migration is successful and stable.