# 🚀 Deployment Guide - VARDA Lead Generation Scraper

This guide covers multiple deployment options to keep your scraper running 24/7, even when your laptop is off.

## 📋 Table of Contents

1. [Streamlit Cloud (Easiest - FREE)](#streamlit-cloud-easiest---free)
2. [Docker Deployment](#docker-deployment)
3. [VPS/Cloud Server](#vpscloud-server)
4. [Railway.app](#railwayapp)
5. [Heroku](#heroku)

---

## 🌐 Streamlit Cloud (Easiest - FREE)

**Best for:** Quick deployment, free hosting, automatic HTTPS

### Prerequisites
- GitHub account
- Streamlit Cloud account (free): https://streamlit.io/cloud

### Steps

1. **Push your code to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/varda-scraper.git
   git push -u origin main
   ```

2. **Go to Streamlit Cloud**
   - Visit: https://share.streamlit.io/
   - Click "New app"
   - Connect your GitHub repository
   - Select branch: `main`
   - Main file path: `dashboard.py`

3. **Set Environment Variables**
   - In Streamlit Cloud dashboard, go to "Settings" → "Secrets"
   - Add:
     ```toml
     OPENAI_API_KEY = "your_api_key_here"
     HEADLESS_MODE = "true"
     ACCESS_PASSWORD = "your_password_here"  # Optional: Remove for public access
     ```

4. **Deploy**
   - Click "Deploy"
   - Your app will be live at: `https://YOUR_APP_NAME.streamlit.app`

### ⚠️ Limitations
- Free tier has resource limits (CPU/memory)
- May timeout on very long scraping sessions
- Playwright browsers need to be installed (handled automatically)

---

## 🐳 Docker Deployment

**Best for:** Full control, any cloud provider, scalable

### Option A: Docker on VPS/Cloud Server

1. **Install Docker** (on your server)
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   ```

2. **Build and Run**
   ```bash
   # Build image
   docker build -t varda-scraper .
   
   # Run container
   docker run -d \
     --name varda-scraper \
     -p 8501:8501 \
     -e OPENAI_API_KEY=your_api_key_here \
     -e HEADLESS_MODE=true \
     -v $(pwd)/output:/app/output \
     --restart unless-stopped \
     varda-scraper
   ```

3. **Access**
   - Your app: `http://YOUR_SERVER_IP:8501`
   - Or set up nginx reverse proxy for HTTPS

### Option B: Docker Compose

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  varda-scraper:
    build: .
    ports:
      - "8501:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - HEADLESS_MODE=true
    volumes:
      - ./output:/app/output
    restart: unless-stopped
```

Run:
```bash
docker-compose up -d
```

---

## 🖥️ VPS/Cloud Server

**Best for:** Full control, dedicated resources, custom setup

### Recommended Providers
- **DigitalOcean**: $6/month (Droplet)
- **Linode**: $5/month (Nanode)
- **AWS EC2**: Pay-as-you-go
- **Google Cloud**: Free tier available
- **Azure**: Free tier available

### Setup Steps (Ubuntu/Debian)

1. **Connect to your server**
   ```bash
   ssh root@YOUR_SERVER_IP
   ```

2. **Install dependencies**
   ```bash
   apt update && apt upgrade -y
   apt install -y python3 python3-pip git
   ```

3. **Clone your repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/varda-scraper.git
   cd varda-scraper
   ```

4. **Install Python dependencies**
   ```bash
   pip3 install -r requirements.txt
   playwright install chromium
   playwright install-deps chromium
   ```

5. **Set environment variables**
   ```bash
   export OPENAI_API_KEY="your_api_key_here"
   export HEADLESS_MODE="true"
   ```

6. **Run with screen/tmux (keeps running after disconnect)**
   ```bash
   # Install screen
   apt install screen -y
   
   # Start screen session
   screen -S varda
   
   # Run Streamlit
   streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
   
   # Detach: Press Ctrl+A, then D
   # Reattach: screen -r varda
   ```

7. **Or use systemd service (better)**

   Create `/etc/systemd/system/varda-scraper.service`:
   ```ini
   [Unit]
   Description=VARDA Lead Generation Scraper
   After=network.target

   [Service]
   Type=simple
   User=root
   WorkingDirectory=/root/varda-scraper
   Environment="OPENAI_API_KEY=your_api_key_here"
   Environment="HEADLESS_MODE=true"
   ExecStart=/usr/bin/streamlit run dashboard.py --server.port=8501 --server.address=0.0.0.0
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start:
   ```bash
   systemctl enable varda-scraper
   systemctl start varda-scraper
   systemctl status varda-scraper
   ```

8. **Set up firewall**
   ```bash
   ufw allow 8501/tcp
   ufw enable
   ```

9. **Access your app**
   - `http://YOUR_SERVER_IP:8501`
   - Or set up nginx reverse proxy for HTTPS

---

## 🚂 Railway.app

**Best for:** Easy deployment, automatic HTTPS, pay-as-you-go

### Steps

1. **Sign up**: https://railway.app
2. **Create new project** → "Deploy from GitHub repo"
3. **Select your repository**
4. **Add environment variables**:
   - `OPENAI_API_KEY`: your API key
   - `HEADLESS_MODE`: `true`
5. **Deploy** - Railway auto-detects Dockerfile
6. **Your app**: `https://YOUR_APP_NAME.railway.app`

### Railway Configuration

Create `railway.json` (optional):
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

---

## 🟣 Heroku

**Best for:** Traditional PaaS, easy scaling

### Steps

1. **Install Heroku CLI**: https://devcenter.heroku.com/articles/heroku-cli

2. **Create `Procfile`**:
   ```
   web: streamlit run dashboard.py --server.port=$PORT --server.address=0.0.0.0
   ```

3. **Create `runtime.txt`**:
   ```
   python-3.11.0
   ```

4. **Deploy**:
   ```bash
   heroku login
   heroku create varda-scraper
   heroku config:set OPENAI_API_KEY=your_api_key_here
   heroku config:set HEADLESS_MODE=true
   git push heroku main
   ```

5. **Open app**:
   ```bash
   heroku open
   ```

---

## 🔐 Security & Access Control

### Password Protection

The dashboard includes built-in password protection. To enable it:

**Option 1: Streamlit Cloud Secrets**
```toml
OPENAI_API_KEY = "your_api_key_here"
HEADLESS_MODE = "true"
ACCESS_PASSWORD = "your_secure_password_here"  # Add this line
```

**Option 2: Environment Variable**
```bash
export ACCESS_PASSWORD="your_secure_password_here"
```

**Option 3: Disable (Public Access)**
- Don't set `ACCESS_PASSWORD` or set it to empty string `""`
- App will be publicly accessible

### Access Control Options

1. **Password Protection** (Built-in)
   - Set `ACCESS_PASSWORD` in secrets/env vars
   - Users must enter password to access dashboard
   - **Best for:** Sharing with team/clients

2. **Private Deployment**
   - Deploy on private VPS/server
   - Use firewall to restrict IP access
   - Only allow your IP addresses
   - **Best for:** Personal use only

3. **Public Deployment** (No password)
   - Don't set `ACCESS_PASSWORD`
   - Anyone with the URL can use it
   - ⚠️ **Warning:** They'll use your OpenAI API credits!
   - **Best for:** Public demos (use separate API key)

4. **Streamlit Cloud Private Sharing**
   - Streamlit Cloud allows sharing with specific email addresses
   - Go to app settings → "Share" → Add emails
   - **Best for:** Team collaboration

### Security Best Practices

1. **Never commit API keys**
   - Use `.env` file (add to `.gitignore`)
   - Use environment variables in cloud platforms

2. **Use HTTPS**
   - Set up reverse proxy (nginx) with Let's Encrypt
   - Or use platform-provided HTTPS (Streamlit Cloud, Railway)

3. **Restrict access**
   - Use password protection (built-in)
   - Use firewall rules to restrict IPs (VPS only)
   - Use Streamlit Cloud private sharing

4. **Monitor usage**
   - Check OpenAI API usage dashboard regularly
   - Set up usage alerts if available
   - Review logs for suspicious activity

---

## 📊 Monitoring & Logs

### View logs (Docker)
```bash
docker logs -f varda-scraper
```

### View logs (systemd)
```bash
journalctl -u varda-scraper -f
```

### View logs (Streamlit Cloud)
- Go to your app → "Manage app" → "Logs"

---

## 🐛 Troubleshooting

### Playwright browsers not found
```bash
playwright install chromium
playwright install-deps chromium
```

### Port already in use
Change port in `docker-compose.yml` or systemd service:
```bash
--server.port=8502
```

### Memory issues
- Increase Docker memory limit
- Reduce `MAX_REVIEWS_PER_BUSINESS` in config
- Use smaller VPS instance

### Timeout errors
- Increase timeout in Streamlit Cloud settings
- Use VPS for longer-running scrapes

---

## 💰 Cost Comparison

| Platform | Cost | Best For |
|----------|------|----------|
| Streamlit Cloud | FREE | Quick deployment, testing |
| Railway.app | $5-20/month | Easy deployment, auto-scaling |
| DigitalOcean | $6/month | Full control, dedicated resources |
| Heroku | $7-25/month | Traditional PaaS |
| AWS EC2 | $5-50/month | Enterprise, scalable |

---

## ✅ Quick Start Checklist

- [ ] Code pushed to GitHub
- [ ] Environment variables set (OPENAI_API_KEY)
- [ ] HEADLESS_MODE=true for cloud
- [ ] Playwright browsers installed
- [ ] Firewall configured (if VPS)
- [ ] HTTPS set up (recommended)
- [ ] Monitoring/logs configured
- [ ] Test deployment

---

## 📞 Need Help?

- Check logs for errors
- Verify environment variables are set
- Ensure Playwright browsers are installed
- Check firewall/port settings
- Review platform-specific documentation
