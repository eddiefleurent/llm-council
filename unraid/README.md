# Unraid Installation Guide

## Installation via Template

1. Download the template XML:
   ```bash
   wget -P /boot/config/plugins/dockerMan/templates-user/ \
     https://raw.githubusercontent.com/eddiefleurent/llm-council/main/unraid/llm-council-template.xml
   ```

2. Reload Docker templates in Unraid UI
3. Go to **Docker** tab → **Add Container** → **User Templates**
4. Select **llm-council**
5. Fill in your API keys and ports
6. Click **Apply**

The container will be available at `http://your-unraid-ip:5173`

## Or Use Docker Compose

See the main [deployment guide](../deploy/README.md) for docker-compose instructions that work on any system including Unraid.

## Configuration

### Required Settings
- **OpenRouter API Key**: Get from https://openrouter.ai/keys
  - Used to query LLM models
  - Without this, the app won't function

### Optional Settings
- **Groq API Key**: Get from https://console.groq.com/keys
  - Enables voice transcription feature
  - App works fine without it

### Data Storage
- Default: `/mnt/user/appdata/llm-council/data`
- This stores your conversation history
- Make sure this directory is on your array for persistence

### Ports
- **5173**: Web UI (Frontend)
- **8001**: API Server (Backend)
- Change if these ports conflict with other containers

## Accessing via Tailscale

If you have Tailscale running on Unraid:
- Access at `http://unraid:5173` (replace `unraid` with your Tailscale hostname)
- No port forwarding needed
- Works from anywhere on your Tailnet

## Troubleshooting

### Container won't start
1. Check logs in Unraid Docker tab
2. Verify **OPENROUTER_API_KEY** is set
3. Check ports aren't already in use

### Can't access web UI
1. Verify container is running (green icon in Docker tab)
2. Check firewall settings
3. Try accessing from Unraid server itself: `http://localhost:5173`

### Data not persisting
1. Verify data directory exists: `/mnt/user/appdata/llm-council/data`
2. Check directory permissions
3. Make sure directory is on the array, not cache-only

## Updating

Unraid will notify you when updates are available in the Docker tab. Click **Update** to pull the latest image.

Or manually:
```bash
docker pull g0dfather/llm-council:latest
```

Then restart the container from the Docker tab.
