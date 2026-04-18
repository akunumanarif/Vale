# Wan Animate Move — Web App

Full-stack web app for `fal-ai/wan/v2.2-14b/animate/move`.  
Upload a character image + a drive video → get an animated video back.

## Stack
- **Backend**: FastAPI + httpx (Python 3.11)
- **Frontend**: Vanilla HTML/CSS/JS (no build step, no Node needed)
- **Deploy**: Docker + docker-compose

---

## Deploy via Termux (no laptop)

### Prerequisites on VPS
```bash
# Make sure Docker & docker-compose are installed
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable docker && sudo systemctl start docker
sudo usermod -aG docker $USER
```

### From Termux

**Option A — Using the deploy script:**
```bash
# Install ssh in Termux if needed
pkg install openssh

# Edit deploy.sh with your VPS details
nano deploy.sh
# Change VPS_USER, VPS_HOST, VPS_PORT

bash deploy.sh
```

**Option B — Manual SSH (step by step):**
```bash
# 1. SSH into VPS
ssh user@your.vps.ip

# 2. Create directory
mkdir -p /opt/wan-animate && cd /opt/wan-animate

# 3. Create files manually (or use git clone if you push this to GitHub)
# Copy each file content from your phone...

# 4. Build & run
docker compose up -d --build

# 5. Check logs
docker compose logs -f
```

**Option C — Git (recommended if you push this repo):**
```bash
# On VPS
git clone https://github.com/YOUR_USER/wan-animate.git /opt/wan-animate
cd /opt/wan-animate
docker compose up -d --build
```

---

## Usage

1. Open `http://your.vps.ip:8000` in browser
2. Enter your **FAL API Key** (from fal.ai dashboard) in the top bar
3. Upload a **character image** (PNG/JPG) and a **drive video** (MP4)
   - Or paste direct URLs instead
4. Choose resolution (720p recommended) and inference steps
5. Click **Generate Animated Video**
6. Wait ~2–5 minutes for the job to complete
7. Download the result video

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `FAL_KEY` | Optional | Server-side FAL key fallback. Users can also enter it in the UI. |

```bash
# Set in .env file:
FAL_KEY=fal_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the frontend |
| `GET` | `/health` | Health check |
| `POST` | `/api/animate` | Submit generation job |
| `GET` | `/api/jobs/{job_id}` | Poll job status |
| `GET` | `/api/jobs` | List all jobs |

### POST /api/animate

Form data fields:
- `image_file` — image upload (optional if `image_url` provided)
- `video_file` — video upload (optional if `video_url` provided)
- `image_url` — direct image URL (alternative to file)
- `video_url` — direct video URL (alternative to file)
- `resolution` — `480p` / `580p` / `720p` (default: `720p`)
- `num_inference_steps` — 10–50 (default: `30`)

Headers:
- `X-Fal-Key: your_fal_key` — per-request FAL key (entered from UI)

---

## Port / Firewall

If your VPS uses UFW:
```bash
sudo ufw allow 8000/tcp
```

For nginx reverse proxy (optional):
```nginx
server {
    listen 80;
    server_name your.domain.com;
    
    client_max_body_size 200M;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
}
```
