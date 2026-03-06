# Deploy Django To AWS Lightsail (Ubuntu)

This guide assumes:
- Domain already points to your Lightsail public IP.
- Project path is `/var/www/XU-Portfolio`.
- Python 3.13 is available.

## 1. System packages

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip nginx certbot python3-certbot-nginx
```

## 2. App setup

```bash
sudo mkdir -p /var/www
cd /var/www
sudo git clone <your-repo-url> XU-Portfolio
cd XU-Portfolio

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create `.env` from template:

```bash
cp .env.example .env
```

Set at least:
- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY=<strong random key>`
- `DJANGO_ALLOWED_HOSTS=xuzhihui-resume.com,www.xuzhihui-resume.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://xuzhihui-resume.com,https://www.xuzhihui-resume.com`

## 3. Migrate and collect static

```bash
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

## 4. Gunicorn systemd service

Create `/etc/systemd/system/xu-portfolio.service`:

```ini
[Unit]
Description=XU Portfolio Django Service
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/XU-Portfolio
EnvironmentFile=/var/www/XU-Portfolio/.env
ExecStart=/var/www/XU-Portfolio/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable service:

```bash
sudo chown -R www-data:www-data /var/www/XU-Portfolio
sudo systemctl daemon-reload
sudo systemctl enable xu-portfolio
sudo systemctl start xu-portfolio
sudo systemctl status xu-portfolio
```

## 5. Nginx reverse proxy

Create `/etc/nginx/sites-available/xu-portfolio`:

```nginx
server {
    listen 80;
    server_name xuzhihui-resume.com www.xuzhihui-resume.com;

    location /static/ {
        alias /var/www/XU-Portfolio/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable site:

```bash
sudo ln -s /etc/nginx/sites-available/xu-portfolio /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 6. Enable HTTPS

```bash
sudo certbot --nginx -d xuzhihui-resume.com -d www.xuzhihui-resume.com
```

After certificate install, verify:

```bash
curl -I https://xuzhihui-resume.com
```

## 7. Update flow

```bash
cd /var/www/XU-Portfolio
source .venv/bin/activate
git pull
pip install -r requirements.txt
export $(grep -v '^#' .env | xargs)
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart xu-portfolio
```
