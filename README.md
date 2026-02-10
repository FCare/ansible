# Ansible - Traefik Network Deployment

**Ansible** - Named after Ursula K. Le Guin's instantaneous communication device from the Hainish Cycle, this deployment connects all your Docker services through a unified Traefik reverse proxy network.

## 🌐 Architecture

```
                               ┌─────────────────┐
                               │     Traefik     │
                               │  (Reverse Proxy) │
                               └────────┬────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
          ┌─────────▼──────┐   ┌───────▼───────┐   ┌──────▼──────┐
          │ Voight-Kampff  │   │     Immich     │   │  TTS/STT/   │
          │  (Auth Service) │   │   (Photos)     │   │  LLM/Asst   │
          └────────────────┘   └────────────────┘   └─────────────┘
               API Keys         Own Auth System      Protected by VK
```

### Services

1. **Traefik** (`traefik.mon_url.com`) - Reverse proxy with automatic HTTPS
2. **Voight-Kampff** (`auth.mon_url.com`) - API Key authentication service
3. **Immich** (`photos.mon_url.com`) - Photo management (uses built-in auth)
4. **TTS Service** (`tts.mon_url.com`) - Text-to-Speech (protected by API keys)
5. **STT Service** (`stt.mon_url.com`) - Speech-to-Text (protected by API keys)
6. **LLM Service** (`llm.mon_url.com`) - Language Model (protected by API keys)
7. **Assistant Backend** (`assistant.mon_url.com`) - Assistant API (protected by API keys)

## 🔐 Authentication Strategy

### Immich
- Uses its **own authentication system**
- No additional API key layer
- Compatible with the Immich Android app out of the box

### Other Services (TTS, STT, LLM, Assistant)
- Protected by **Voight-Kampff** API key authentication
- Fine-grained access control per service
- Multiple API keys with different scopes

## 🚀 Getting Started

### Prerequisites

- Docker and Docker Compose installed
- A domain name pointing to your server
- Ports 80 and 443 available

### Installation

1. **Clone/Navigate to the ansible directory**
   ```bash
   cd ansible
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Update:
   - `LETSENCRYPT_EMAIL` - Your email for Let's Encrypt
   - `VK_SECRET_KEY` - Generate a random secret (min 32 chars)
   - `IMMICH_DB_PASSWORD` - Strong password for Immich database
   - Replace `mon_url.com` with your actual domain in `docker-compose.yml`

3. **Update your domain in docker-compose.yml**
   ```bash
   sed -i 's/mon_url.com/yourdomain.com/g' docker-compose.yml
   ```

4. **Update Traefik email**
   ```bash
   nano traefik/traefik.yml
   # Change: email: your-email@example.com
   ```

5. **Create required directories and set permissions**
   ```bash
   mkdir -p traefik/logs
   touch traefik/acme.json
   chmod 600 traefik/acme.json
   ```

6. **Update your service images**
   Edit `docker-compose.yml` and replace:
   - `your-tts-image:latest`
   - `your-stt-image:latest`
   - `your-llm-image:latest`
   - `your-assistant-image:latest`
   
   With your actual Docker images.

7. **Start the services**
   ```bash
   docker-compose up -d
   ```

8. **Check logs**
   ```bash
   docker-compose logs -f
   ```

## 🔑 Managing API Keys

### Create an API Key

```bash
curl -X POST https://auth.mon_url.com/keys \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "mobile-app",
    "user": "john",
    "scopes": ["tts", "stt", "llm", "assistant"],
    "expires_in_days": 365
  }'
```

Response:
```json
{
  "id": 1,
  "key_name": "mobile-app",
  "api_key": "kXy8vZ3mQ9wR5tN7pL4jH2fG6sA1dK0bC...",
  "user": "john",
  "scopes": ["tts", "stt", "llm", "assistant"],
  "is_active": true,
  "created_at": "2026-02-10T15:00:00",
  "last_used": null,
  "expires_at": "2027-02-10T15:00:00"
}
```

**⚠️ Important:** Save the `api_key` value - it won't be shown again!

### List All API Keys

```bash
curl https://auth.mon_url.com/keys
```

### Delete an API Key

```bash
curl -X DELETE https://auth.mon_url.com/keys/1
```

### Enable/Disable an API Key

```bash
curl -X PATCH https://auth.mon_url.com/keys/1/toggle
```

## 📱 Using API Keys

### Making Requests to Protected Services

Include the API key in the `Authorization` header:

```bash
curl https://tts.mon_url.com/api/synthesize \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world"}'
```

### Python Example

```python
import requests

API_KEY = "your-api-key-here"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# TTS Service
response = requests.post(
    "https://tts.mon_url.com/api/synthesize",
    headers=headers,
    json={"text": "Hello world"}
)

# STT Service
response = requests.post(
    "https://stt.mon_url.com/api/transcribe",
    headers=headers,
    files={"audio": open("audio.wav", "rb")}
)
```

## 🎯 Scopes and Permissions

Each API key can have specific scopes limiting access to services:

- `tts` - Text-to-Speech service only
- `stt` - Speech-to-Text service only
- `llm` - Language Model service only
- `assistant` - Assistant backend only
- `*` - All services (wildcard)

**Example: Create a key with limited access**
```bash
curl -X POST https://auth.mon_url.com/keys \
  -H "Content-Type: application/json" \
  -d '{
    "key_name": "tts-only-key",
    "user": "demo",
    "scopes": ["tts"],
    "expires_in_days": 30
  }'
```

This key can **only** access `tts.mon_url.com`, attempts to access other services will be denied.

## 🔧 Maintenance

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f traefik
docker-compose logs -f voight-kampff
docker-compose logs -f immich

# Traefik access logs
tail -f traefik/logs/access.log
```

### Restart Services

```bash
# All services
docker-compose restart

# Specific service
docker-compose restart traefik
```

### Update Services

```bash
docker-compose pull
docker-compose up -d
```

### Backup

```bash
# Backup Voight-Kampff database (API keys)
cp voight-kampff/data/voight-kampff.db voight-kampff.db.backup

# Backup Immich data
tar -czf immich-backup.tar.gz immich/

# Backup Traefik certificates
cp traefik/acme.json acme.json.backup
```

## 🐛 Troubleshooting

### SSL Certificates Not Generated

1. Check Traefik logs: `docker-compose logs traefik`
2. Verify your domain DNS points to your server
3. Ensure ports 80 and 443 are open
4. Check `traefik/acme.json` permissions: `chmod 600 traefik/acme.json`

### API Key Not Working

1. Verify the key exists: `curl https://auth.mon_url.com/keys`
2. Check it's active and not expired
3. Verify the scope includes the service you're accessing
4. Check Voight-Kampff logs: `docker-compose logs voight-kampff`

### Service Not Accessible

1. Check if container is running: `docker-compose ps`
2. Verify Traefik labels: `docker inspect <container_name>`
3. Check Traefik dashboard: `https://traefik.mon_url.com`
4. Review Traefik logs: `docker-compose logs traefik`

### Immich App Connection Issues

Immich uses its own authentication - **do NOT add API keys**. Use the credentials created in Immich's web interface.

## 📊 Network Details

- **Network Name:** `ansible`
- **Driver:** bridge
- All services communicate internally using container names
- Only Traefik exposes ports 80/443 to the host

## 🔐 Security Recommendations

1. **Change all default passwords** in `.env`
2. **Use strong API keys** (automatically generated)
3. **Set expiration dates** for temporary access
4. **Regularly review** active API keys
5. **Enable firewall** to only allow ports 80/443
6. **Keep services updated** with `docker-compose pull`
7. **Monitor access logs** regularly
8. **Backup** the Voight-Kampff database

## 📚 References

- [Traefik Documentation](https://doc.traefik.io/traefik/)
- [Immich Documentation](https://immich.app/docs/overview/introduction)
- [Let's Encrypt](https://letsencrypt.org/)

---

**Named after:** Ansible (Ursula K. Le Guin's Hainish Cycle) - Instantaneous communication across vast distances  
**Authentication:** Voight-Kampff (Blade Runner) - The test to determine humanity
