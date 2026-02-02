# LLM Council Deployment Guide

## General Docker Deployment

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+ (optional but recommended)

### Using Docker Compose (Recommended)

1. Clone repository:
   ```bash
   git clone https://github.com/eddiefleurent/llm-council.git
   cd llm-council
   ```

2. Copy and edit environment variables:
   ```bash
   cp deploy/.env.example deploy/.env
   nano deploy/.env  # Add your API keys
   ```

3. Create data directory:
   ```bash
   mkdir -p data
   ```

4. Start container:
   ```bash
   docker compose up -d
   ```

5. Access at `http://localhost:5173`

### Using Docker Run (Alternative)

```bash
docker run -d \
  --name llm-council \
  -p 5173:5173 \
  -p 8001:8001 \
  -v ./data:/app/data \
  -e OPENROUTER_API_KEY=sk-or-v1-your-key-here \
  -e GROQ_API_KEY=gsk_your-key-here \
  --restart unless-stopped \
  g0dfather/llm-council:latest
```

## Unraid Deployment

### Option A: Docker Compose on Unraid

1. SSH into Unraid server
2. Create directory:
   ```bash
   mkdir -p /mnt/user/appdata/llm-council/data
   cd /mnt/user/appdata/llm-council
   ```

3. Create `docker-compose.yml`:
   ```yaml
   services:
     llm-council:
       image: g0dfather/llm-council:latest
       container_name: llm-council
       restart: unless-stopped
       ports:
         - "5173:5173"
         - "8001:8001"
       volumes:
         - ./data:/app/data
       environment:
         - OPENROUTER_API_KEY=sk-or-v1-your-key-here
         # Optional: Groq API key for voice transcription
         - GROQ_API_KEY=
         - PYTHONUNBUFFERED=1
   ```

4. Start container:
   ```bash
   docker compose up -d
   ```

5. Access at `http://your-unraid-ip:5173`

For Unraid-specific details, see [unraid/README.md](../unraid/README.md).

## Troubleshooting

### Container won't start
```bash
# View logs
docker logs llm-council

# Common issues:
# - Missing OPENROUTER_API_KEY
# - Port already in use (change host ports)
# - Volume permission issues
```

### Can't access web UI
```bash
# Check container is running
docker ps | grep llm-council

# Check ports are exposed
docker port llm-council

# Test backend
curl http://localhost:8001/

# Test frontend
curl http://localhost:5173/
```

### Data not persisting
```bash
# Verify volume mount is correct
docker inspect llm-council | grep -A5 Mounts

# Check data directory permissions (adjust path for your setup)
ls -la ./data/  # For Docker Compose
# or
ls -la /mnt/user/appdata/llm-council/data/  # Unraid example

# Ensure container has write permissions
docker exec llm-council ls -la /app/data

```

## Updating

### Pull latest image
```bash
docker compose pull
docker compose up -d
```

### Or with docker run
```bash
docker pull g0dfather/llm-council:latest
docker stop llm-council
docker rm llm-council
# Then run the docker run command again
```

## Environment Variables

| Variable             | Required | Description |
|----------------------|----------|-------------|
| `OPENROUTER_API_KEY` | Yes      | Your OpenRouter API key from [https://openrouter.ai/keys](https://openrouter.ai/keys) |
| `GROQ_API_KEY`       | No       | Groq API key for voice transcription from [https://console.groq.com/keys](https://console.groq.com/keys) |

## Ports

| Port | Service  | Description           |
|------|----------|-----------------------|
| 5173 | Frontend | Web UI (React app)    |
| 8001 | Backend  | API server (FastAPI)  |

## Volume Mounts

| Container Path | Description                                  |
|----------------|----------------------------------------------|
| `/app/data`    | Persistent conversation storage (JSON files) |

Recommended host path for Unraid: `/mnt/user/appdata/llm-council/data`
