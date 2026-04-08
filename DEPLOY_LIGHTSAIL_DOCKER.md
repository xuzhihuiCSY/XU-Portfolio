# Deploy On AWS Lightsail With Docker

This setup runs:
- Django + Gunicorn (`web`)
- PostgreSQL (`db`)
- Nginx reverse proxy (`nginx`)
- V2Ray as optional profile (`v2ray`)

## 1. Provision Lightsail instance

Recommended: Ubuntu with at least 2 GB RAM.

Open firewall ports:
- 22 (SSH)
- 80 (HTTP)
- 443 (HTTPS)
- 10086 (only if you enable V2Ray profile)

## 2. Install Docker and Compose plugin

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

## 3. Pull project and configure environment

```bash
cd /home/ubuntu
git clone <your-repo-url> XU-Portfolio
cd XU-Portfolio
cp .env.example .env
```

Edit `.env` and set at minimum:
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `POSTGRES_PASSWORD`
- `LETSENCRYPT_EMAIL`

## 4. Start services

```bash
docker compose up -d --build
```

Optional: start VPN service too

```bash
docker compose --profile vpn up -d
```

## 5. Enable HTTPS (container Nginx + Let's Encrypt)

Make sure DNS A records for `xuzhihui-resume.com` and `www.xuzhihui-resume.com` already point to this instance.

Issue certificate (webroot validation through running nginx):

```bash
docker compose run --rm --profile tls certbot certonly \
  --webroot -w /var/www/certbot \
  -d xuzhihui-resume.com -d www.xuzhihui-resume.com \
  --email "$LETSENCRYPT_EMAIL" --agree-tos --no-eff-email
```

Switch nginx config to SSL config and restart:

```bash
cp docker/nginx/default-ssl.conf docker/nginx/default.conf
docker compose up -d nginx
```

After HTTPS is up, set `DJANGO_SECURE_SSL_REDIRECT=True` in `.env` and restart web:

```bash
docker compose up -d web
```

Renew certificates (run periodically, e.g. cron):

```bash
docker compose run --rm --profile tls certbot renew --webroot -w /var/www/certbot
docker compose up -d nginx
```

## 6. Verify

```bash
docker compose ps
docker compose logs -f web
docker compose logs -f nginx
```

Check app:

```bash
curl -I http://127.0.0.1
curl -I https://xuzhihui-resume.com
```

## 7. Update flow

```bash
cd /home/ubuntu/XU-Portfolio
git pull
docker compose up -d --build
```

## 8. Backup PostgreSQL

```bash
docker exec -t xu_db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%F).sql
```

Use cron to run daily backups and prune old files.
