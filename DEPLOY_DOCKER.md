# 🐳 Docker Deployment Guide - VARDA Scraper

Docker deployment gives you **full control** and **reliable Playwright support**. This is the recommended approach.

## Quick Start (5 minutes)

### Option 1: Railway.app (Easiest Docker Deployment)

1. **Sign up**: https://railway.app (free trial)
2. **Create new project** → "Deploy from GitHub repo"
3. **Select your repository**: `varda-scraper`
4. **Railway auto-detects Dockerfile** - no configuration needed!
5. **Add environment variables**:
   - `OPENAI_API_KEY`: your API key
   - `HEADLESS_MODE`: `true`
   - `ACCESS_PASSWORD`: your password (optional)
6. **Deploy** - Railway builds and runs your Docker container
7. **Done!** Your app is live at `https://YOUR_APP.railway.app`

**Why Railway?**
- ✅ Automatic HTTPS
- ✅ Auto-deploys on git push
- ✅ Free tier available
- ✅ Handles Docker perfectly
- ✅ No configuration needed

---

### Option 2: Render.com (Free Docker Hosting)

1. **Sign up**: https://render.com
2. **New** → **Web Service**
3. **Connect GitHub** → Select `varda-scraper`
4. **Settings**:
   - **Build Command**: `docker build -t varda-scraper .`
   - **Start Command**: `docker run -p 8501:8501 varda-scraper`
   - Or use **Docker** option (auto-detects Dockerfile)
5. **Environment Variables**:
   - `OPENAI_API_KEY`
   - `HEADLESS_MODE=true`
   - `ACCESS_PASSWORD` (optional)
6. **Deploy**

---

### Option 3: DigitalOcean App Platform

1. **Sign up**: https://cloud.digitalocean.com
2. **Create** → **App** → **GitHub**
3. **Select repository**: `varda-scraper`
4. **Edit** → **Components** → **Add Component** → **Web Service**
5. **Settings**:
   - **Build Command**: `docker build -t varda-scraper .`
   - **Run Command**: `docker run -p 8080:8501 varda-scraper`
   - **HTTP Port**: `8080`
6. **Environment Variables**: Add your keys
7. **Deploy**

---

### Option 4: Local Docker (For Testing)

1. **Build the image**:
   ```bash
   docker build -t varda-scraper .
   ```

2. **Run the container**:
   ```bash
   docker run -d \
     --name varda-scraper \
     -p 8501:8501 \
     -e OPENAI_API_KEY=your_api_key_here \
     -e HEADLESS_MODE=true \
     -e ACCESS_PASSWORD=your_password \
     -v $(pwd)/output:/app/output \
     --restart unless-stopped \
     varda-scraper
   ```

3. **Access**: http://localhost:8501

---

### Option 5: Docker Compose (Local/Server)

1. **Create `.env` file**:
   ```env
   OPENAI_API_KEY=your_api_key_here
   HEADLESS_MODE=true
   ACCESS_PASSWORD=your_password
   ```

2. **Run**:
   ```bash
   docker-compose up -d
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

---

## Why Docker is Better

✅ **Full Control**: Install any system packages  
✅ **Reliable**: Playwright browsers install correctly  
✅ **Consistent**: Same environment everywhere  
✅ **Portable**: Run anywhere Docker runs  
✅ **Production-Ready**: Used by major platforms  

---

## Cost Comparison

| Platform | Cost | Best For |
|----------|------|----------|
| **Railway.app** | $5-20/month | Easiest Docker deployment |
| **Render.com** | FREE tier | Free Docker hosting |
| **DigitalOcean** | $5-12/month | Professional hosting |
| **Local Docker** | FREE | Testing/development |

---

## Troubleshooting

**Build fails?**
- Check Dockerfile syntax
- Ensure all dependencies are listed
- Check build logs

**Browsers not working?**
- Dockerfile installs browsers during build
- Should work out of the box

**Port issues?**
- Make sure port 8501 is exposed
- Check firewall settings

---

## Recommended: Railway.app

**Easiest option** - Just connect GitHub and deploy. No configuration needed!

1. Go to: https://railway.app
2. New Project → Deploy from GitHub
3. Select `varda-scraper`
4. Add environment variables
5. Done!

Your app will be live in 3-5 minutes with full Playwright support! 🚀
