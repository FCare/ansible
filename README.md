# Ansible - Traefik Network Deployment

**Ansible** - Named after Ursula K. Le Guin's instantaneous communication device from the Hainish Cycle, this deployment provides a unified Traefik reverse proxy network for external services.

## 🌐 Architecture

```
                               ┌─────────────────┐
                               │     Traefik     │
                               │  (Reverse Proxy) │
                               └────────┬────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
          ┌─────────▼──────┐                       ┌──────▼──────┐
          │ Voight-Kampff  │                       │   External   │
          │ (Auth Service) │                       │   Services   │
          └────────────────┘                       └─────────────┘
           API Keys + Cookies                   Protected by Hybrid Auth
```

### Current Services (caronboulme.fr)

1. **Traefik Dashboard** (`traefik.caronboulme.fr`) - Reverse proxy dashboard (admin only)
2. **Voight-Kampff Auth** (`auth.caronboulme.fr`) - Hybrid authentication service (API keys + web interface)
3. **TheBrain** (`thebrain.caronboulme.fr`) - vLLM FastAPI server (protected)
4. **Unmute Talk** (`unmute-talk.caronboulme.fr`) - TTS service (protected)
5. **Unmute Transcript** (`unmute-transcript.caronboulme.fr`) - STT service (protected)
6. **Chatterbox** (`chatterbox.caronboulme.fr`) - Alternative TTS service (protected)
7. **Photos** (`photos.caronboulme.fr`) - Immich photo management (has its own auth)

## 🔐 Hybrid Authentication Strategy

Services are protected by **Voight-Kampff** hybrid authentication:
- **API Keys** for programmatic access (Bearer tokens)
- **Web Interface** with cookies for browser access
- **Admin detection** for sensitive services (like Traefik dashboard)
- **Service-specific scopes** and access control

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose installed
- External services (voight-kampff, thebrain, etc.) running and connected to the `ansible` network
- A domain name pointing to your server
- Ports 80 and 443 available

### Installation

1. **Clone/Navigate to the ansible directory**
   ```bash
   cd /path/to/Ansible
   ```

2. **Update Traefik email for Let's Encrypt certificates**
   ```bash
   nano traefik.yml
   # Change line 33: email: your-email@example.com
   ```

3. **Update your domain in configuration files**
   ```bash
   # Update traefik.yml and dynamic.yml
   sed -i 's/caronboulme.fr/yourdomain.com/g' traefik.yml dynamic.yml
   ```

4. **Create required directories and set permissions**
   ```bash
   mkdir -p traefik/logs
   touch traefik/acme.json
   chmod 600 traefik/acme.json
   ```

5. **Configure your services in dynamic.yml**
   Edit [`dynamic.yml`](dynamic.yml:1) to:
   - Update service hostnames to your domain
   - Configure service backends (container names and ports)
   - Adjust middleware settings as needed

6. **Start Traefik**
   ```bash
   docker-compose up -d
   ```

7. **Connect your external services**
   Ensure your services are connected to the `ansible` network:
   ```bash
   docker network connect ansible your-service-container
   ```

8. **Check logs**
   ```bash
   docker-compose logs -f
   ```

## 🔑 Authentication & Access

### Web Interface Access

Visit the Voight-Kampff web interface for user-friendly API key management:
```bash
https://auth.caronboulme.fr
```

### API Key Management

**Note:** API key creation/management is handled by the external Voight-Kampff service. Refer to the Voight-Kampff documentation for detailed API key operations.

### Making Requests to Protected Services

Include the API key in the `Authorization` header:

```bash
curl https://thebrain.caronboulme.fr/v1/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen", "prompt": "Hello"}'
```

### Python Example

```python
import requests

API_KEY = "your-api-key-here"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# TheBrain (LLM) Service
response = requests.post(
    "https://thebrain.caronboulme.fr/v1/completions",
    headers=headers,
    json={"model": "qwen", "prompt": "Hello world"}
)

# TTS Service (Unmute Talk)
response = requests.post(
    "https://unmute-talk.caronboulme.fr/tts",
    headers=headers,
    json={"text": "Hello world"}
)

# STT Service (Unmute Transcript)
with open("audio.wav", "rb") as audio_file:
    response = requests.post(
        "https://unmute-transcript.caronboulme.fr/transcribe",
        headers=headers,
        files={"audio": audio_file}
    )
```

## 🎯 Hybrid Authentication

The system supports both API keys and web authentication:

- **API Keys** - For programmatic access via Bearer tokens
- **Web Cookies** - For browser-based access (automatically handled)
- **Admin Detection** - Admin users can access sensitive services like Traefik dashboard
- **Service Scopes** - Fine-grained access control per service

## 🔧 Maintenance

### View Logs

```bash
# Traefik logs
docker-compose logs -f traefik

# Traefik access logs
tail -f traefik/logs/access.log

# Check all external services connected to ansible network
docker ps --filter "network=ansible"
```

### Restart Services

```bash
# Restart Traefik
docker-compose restart traefik

# Update Traefik
docker-compose pull traefik
docker-compose up -d traefik
```

### Configuration Updates

```bash
# Reload dynamic.yml changes (automatic with file provider)
# Changes are picked up within seconds

# For traefik.yml changes, restart is required:
docker-compose restart traefik
```

### Backup

```bash
# Backup Traefik certificates
cp traefik/acme.json acme.json.backup

# Backup configuration
cp dynamic.yml dynamic.yml.backup
cp traefik.yml traefik.yml.backup
```

## 🐛 Troubleshooting

### SSL Certificates Not Generated

1. Check Traefik logs: `docker-compose logs traefik`
2. Verify your domain DNS points to your server
3. Ensure ports 80 and 443 are open
4. Check `traefik/acme.json` permissions: `chmod 600 traefik/acme.json`

### Service Not Accessible

1. Check if external service is running and connected to network:
   ```bash
   docker network inspect ansible
   ```
2. Verify service configuration in [`dynamic.yml`](dynamic.yml:1)
3. Check Traefik dashboard: `https://traefik.caronboulme.fr` (admin access required)
4. Review Traefik logs: `docker-compose logs traefik`

### Authentication Issues

1. Check Voight-Kampff service is running and accessible
2. Verify the service can reach `http://voight-kampff:8080/verify`
3. Test authentication endpoint:
   ```bash
   curl -H "Authorization: Bearer YOUR_KEY" https://auth.caronboulme.fr/verify
   ```

## 📊 Network Details

- **Network Name:** `ansible`
- **Driver:** bridge
- **Purpose:** Connect external services to Traefik reverse proxy
- External services must join this network to be accessible through Traefik
- Only Traefik exposes ports 80/443 to the host

### Connecting External Services

```bash
# Connect existing service to ansible network
docker network connect ansible your-service-container

# Or in docker-compose.yml:
networks:
  ansible:
    external: true
    name: ansible
```

## 🔐 Security Recommendations

1. **Configure strong authentication** in Voight-Kampff
2. **Regularly review** active API keys and users
3. **Enable firewall** to only allow ports 80/443
4. **Keep Traefik updated** with `docker-compose pull`
5. **Monitor access logs** regularly
6. **Secure admin access** to Traefik dashboard
7. **Use HTTPS everywhere** (automatically handled by Traefik)
8. **Review service configurations** in [`dynamic.yml`](dynamic.yml:1) regularly

## 📚 References

- [Traefik v3 Documentation](https://doc.traefik.io/traefik/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Docker Networks](https://docs.docker.com/network/)

---

**Named after:** Ansible (Ursula K. Le Guin's Hainish Cycle) - Instantaneous communication across vast distances
**Authentication:** Voight-Kampff (Blade Runner) - The test to determine humanity
