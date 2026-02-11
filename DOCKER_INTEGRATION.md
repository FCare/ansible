# Separate Docker Compose Integration Guide

This guide details how to integrate your existing services to the Ansible network **while keeping your docker-compose files separate**.

This approach is ideal if:
- ✅ You already have well-organized docker-compose files
- ✅ You want to manage your services independently
- ✅ You develop/test your services separately
- ✅ You have complex configurations to preserve

## 🏗️ Important: Ansible is a Proxy Only

**Key Understanding**: The Ansible project is **only a Traefik proxy**. It doesn't contain your services - it routes traffic to your external services.

```
Ansible Project (Traefik Only) → Your Services (Separate Projects)
```

## 📁 Recommended Directory Structure

```
/home/user/
├── ansible/                    # Traefik proxy deployment
│   ├── docker-compose.yml     # Only contains Traefik
│   ├── traefik.yml
│   └── dynamic.yml            # Service routing configuration
├── services/
│   ├── voight-kampff/         # Your authentication service
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   └── src/
│   ├── tts/                   # Your TTS service
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   └── src/
│   ├── stt/                   # Your STT service
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   └── src/
│   ├── llm/                   # Your LLM service
│   │   ├── docker-compose.yml
│   │   └── models/
│   └── assistant/             # Your assistant backend
│       ├── docker-compose.yml
│       └── src/
```

## 🔧 Step 1: Modify Your Existing Docker Compose Files

### Complete Example for TTS Service

**File: `/home/user/services/tts/docker-compose.yml`**

```yaml
version: '3.8'

# IMPORTANT: Declare ansible network as external
networks:
  ansible:
    external: true
    name: ansible

services:
  tts:
    build: .
    # OR: image: your-tts-image:latest
    container_name: tts-service
    restart: unless-stopped
    
    # ⚠️ IMPORTANT: Connect to ansible network
    networks:
      - ansible
    
    # ❌ DO NOT expose ports (Traefik handles everything)
    # ports:
    #   - "8000:8000"  # ← REMOVE THIS
    
    environment:
      - TTS_MODEL=/models/tts.onnx
      - TTS_VOICE=en-US
      - LOG_LEVEL=info
    
    volumes:
      - ./models:/models
      - ./cache:/cache
      - ./config.yml:/app/config.yml
    
    # ❌ NO TRAEFIK LABELS NEEDED
    # Configuration is done in dynamic.yml of the Ansible project
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Key Changes**:
- ✅ Connect to `ansible` network
- ❌ Remove all port exposures
- ❌ **No Traefik labels** - configuration is in Ansible project's [`dynamic.yml`](dynamic.yml:1)

### Example for STT Service

**File: `/home/user/services/stt/docker-compose.yml`**

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible

services:
  stt:
    image: your-stt-image:v1.2
    container_name: stt-service
    restart: unless-stopped
    networks:
      - ansible
    
    environment:
      - STT_MODEL_PATH=/models/whisper-large-v3
      - STT_LANGUAGE=en
      - CUDA_VISIBLE_DEVICES=0  # If using GPU
    
    volumes:
      - ./models:/models
      - ./audio:/audio
    
    # GPU mount (if needed)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    # No Traefik labels - configuration is in Ansible project's dynamic.yml
```

### Example for LLM Service (vLLM)

**File: `/home/user/services/llm/docker-compose.yml`**

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible

services:
  qwen-api-server:  # This matches the current configuration
    image: vllm/vllm-openai:latest
    container_name: qwen-api-server
    restart: unless-stopped
    networks:
      - ansible
    
    environment:
      - VLLM_MODEL_PATH=/models/qwen
      - VLLM_HOST=0.0.0.0
      - VLLM_PORT=8000
    
    volumes:
      - ./models:/models
      - ./cache:/cache
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    
    # No Traefik labels needed
```

### Example for Voight-Kampff Auth Service

**File: `/home/user/services/voight-kampff/docker-compose.yml`**

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible
  
  # Internal network for database
  vk-internal:
    driver: bridge

services:
  voight-kampff:
    build: .
    container_name: voight-kampff
    restart: unless-stopped
    networks:
      - ansible      # For Traefik access
      - vk-internal   # For database access
    
    environment:
      - DATABASE_URL=sqlite:///data/voight-kampff.db
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_USERS=admin1,admin2
    
    volumes:
      - ./data:/app/data
      - ./config:/app/config
    
    depends_on:
      - vk-db
    
    # No Traefik labels - Voight-Kampff is configured directly in dynamic.yml
  
  # Database (not exposed via Traefik)
  vk-db:
    image: postgres:16
    container_name: vk-db
    restart: unless-stopped
    networks:
      - vk-internal  # Only internal network
    
    environment:
      - POSTGRES_USER=voightkampff
      - POSTGRES_PASSWORD=secure_password
      - POSTGRES_DB=voightkampff
    
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
```

## 🚀 Step 2: Service Startup

### IMPORTANT Startup Order

```bash
# 1. First start Ansible (creates network and Traefik)
cd /home/user/ansible
docker-compose up -d

# Wait for Traefik to be ready
docker-compose logs -f traefik
# Wait to see "Configuration loaded"

# 2. Then start your services in any order
cd /home/user/services/voight-kampff
docker-compose up -d

cd /home/user/services/tts
docker-compose up -d

cd /home/user/services/stt
docker-compose up -d

cd /home/user/services/llm
docker-compose up -d
```

### Step 3: Configure Services in dynamic.yml

After starting your services, add them to the Ansible project's [`dynamic.yml`](dynamic.yml:1):

```yaml
# Add your services to the existing configuration
http:
  routers:
    # Your TTS service
    my-tts:
      rule: "Host(`my-tts.caronboulme.fr`)"
      entryPoints: [websecure]
      tls:
        certResolver: letsencrypt
      service: my-tts-backend
      middlewares: [vk-hybrid]

  services:
    # Your TTS backend
    my-tts-backend:
      loadBalancer:
        servers:
          - url: "http://tts-service:8000"  # Container name from your docker-compose
```

### Automated Startup Script

Create `/home/user/start-all.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Starting Ansible infrastructure..."

# 1. Start Ansible (Traefik only)
cd /home/user/ansible
docker-compose up -d
echo "✅ Traefik proxy started"

# Wait for Traefik to be ready
echo "⏳ Waiting for Traefik..."
sleep 5

# 2. Start external services
echo "🚀 Starting external services..."

cd /home/user/services/voight-kampff
docker-compose up -d
echo "✅ Voight-Kampff started"

cd /home/user/services/tts
docker-compose up -d
echo "✅ TTS started"

cd /home/user/services/stt
docker-compose up -d
echo "✅ STT started"

cd /home/user/services/llm
docker-compose up -d
echo "✅ LLM started"

echo ""
echo "✅ All services are started!"
echo ""
echo "Available services:"
echo "  - https://traefik.caronboulme.fr (Traefik Dashboard - admin only)"
echo "  - https://auth.caronboulme.fr (Voight-Kampff Auth)"
echo "  - Configure your services in /home/user/ansible/dynamic.yml"
echo ""
echo "Next steps:"
echo "  1. Add your service configurations to dynamic.yml"
echo "  2. Restart Traefik: cd /home/user/ansible && docker-compose restart traefik"
```

Make it executable:

```bash
chmod +x /home/user/start-all.sh
```

## 🛑 Stopping Services

### Stop Script

Create `/home/user/stop-all.sh`:

```bash
#!/bin/bash
set -e

echo "🛑 Stopping external services..."

cd /home/user/services/llm
docker-compose down
echo "✅ LLM stopped"

cd /home/user/services/stt
docker-compose down
echo "✅ STT stopped"

cd /home/user/services/tts
docker-compose down
echo "✅ TTS stopped"

cd /home/user/services/voight-kampff
docker-compose down
echo "✅ Voight-Kampff stopped"

cd /home/user/ansible
docker-compose down
echo "✅ Ansible proxy stopped"

echo ""
echo "✅ All services stopped"
```

## 🔄 Restart a Specific Service

```bash
# Restart just the TTS service
cd /home/user/services/tts
docker-compose restart

# Or rebuild and restart
docker-compose up -d --build

# After restarting a service, you may need to restart Traefik
# to refresh service discovery
cd /home/user/ansible
docker-compose restart traefik
```

## 🐛 Debug and Logs

### View Service Logs

```bash
cd /home/user/services/tts
docker-compose logs -f

# Or directly
docker logs -f tts-service
```

### Check Network Connection

```bash
# List containers on the ansible network
docker network inspect ansible

# Should show:
# - ansible-traefik
# - voight-kampff
# - tts-service
# - stt-service
# - qwen-api-server (or your LLM container)
# - your other connected services
```

### Test From Container

```bash
# Enter a container
docker exec -it tts-service sh

# Test connection to Voight-Kampff
curl http://voight-kampff:8080/health
# Should return: {"status":"operational","health":"positive"}

# Test other services
curl http://stt-service:8080/health
curl http://qwen-api-server:8000/health
```

## 🔐 Secrets Management

### Using .env per service

**`/home/user/services/tts/.env`**
```env
TTS_MODEL=tts-v2.onnx
LOG_LEVEL=debug
API_TIMEOUT=30
```

**`/home/user/services/tts/docker-compose.yml`**
```yaml
services:
  tts:
    env_file:
      - .env  # ← Automatically loads variables
```

### Centralize secrets (optional)

Create `/home/user/.env` with all your secrets:

```env
# TTS
TTS_MODEL=tts-v2.onnx

# STT
STT_MODEL=whisper-large-v3

# LLM
VLLM_MODEL=qwen2.5:32b

# Voight-Kampff
VK_SECRET_KEY=super-secret-key-here
DATABASE_PASSWORD=postgres-password-here
```

Reference it in each docker-compose:

```yaml
services:
  tts:
    env_file:
      - ../../.env  # Relative path to central .env
```

## 📊 Centralized Monitoring

### View all services at once

```bash
# Status of all containers
docker ps --filter "network=ansible" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Logs of all services (separate terminals recommended)
docker-compose -f /home/user/ansible/docker-compose.yml logs -f &
docker-compose -f /home/user/services/voight-kampff/docker-compose.yml logs -f &
docker-compose -f /home/user/services/tts/docker-compose.yml logs -f &
docker-compose -f /home/user/services/stt/docker-compose.yml logs -f &
docker-compose -f /home/user/services/llm/docker-compose.yml logs -f
```

### Traefik Dashboard

Access `https://traefik.caronboulme.fr` (admin access required) to see:
- ✅ Status of all services
- ✅ Configured routes
- ✅ SSL certificates
- ✅ Active middlewares

## 🔄 Updating a Service

```bash
# 1. Go to service directory
cd /home/user/services/tts

# 2. Stop the service
docker-compose down

# 3. Update image (if external)
docker-compose pull

# 4. Or rebuild (if local build)
docker-compose build

# 5. Restart
docker-compose up -d

# 6. Check logs
docker-compose logs -f

# 7. If you changed container name/port, update dynamic.yml
# and restart Traefik
cd /home/user/ansible
docker-compose restart traefik
```

## ✅ Migration Checklist

For each existing service:

- [ ] Add `networks: ansible: external: true` at top of docker-compose
- [ ] Add `networks: - ansible` to the service
- [ ] **Remove** or comment all exposed `ports:`
- [ ] **DO NOT add Traefik labels** - configuration is in [`dynamic.yml`](dynamic.yml:1)
- [ ] Test syntax: `docker-compose config`
- [ ] Start: `docker-compose up -d`
- [ ] Verify network: `docker network inspect ansible`
- [ ] Add service to Ansible project's [`dynamic.yml`](dynamic.yml:1)
- [ ] Restart Traefik: `cd /home/user/ansible && docker-compose restart traefik`
- [ ] Test access: `curl https://service.caronboulme.fr/health -H "Authorization: Bearer API_KEY"`

## 🆘 Common Issues

### "network ansible not found"

**Cause**: Ansible is not started or network doesn't exist

**Solution**:
```bash
cd /home/user/ansible
docker-compose up -d
```

### "Container cannot connect to voight-kampff"

**Cause**: Service is not on ansible network

**Solution**: Verify `networks: - ansible` is present in the service

### Service not accessible via Traefik

**Cause**: Service not configured in [`dynamic.yml`](dynamic.yml:1)

**Solution**: Add service configuration to Ansible project's [`dynamic.yml`](dynamic.yml:1)

## 📝 Complete Migration Example

### Before (your existing docker-compose)

```yaml
version: '3.8'

services:
  tts:
    build: .
    ports:
      - "8000:8000"
    environment:
      - MODEL=/models/tts.onnx
    volumes:
      - ./models:/models
```

### After (integrated with Ansible)

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible

services:
  tts:
    build: .
    # ports: - "8000:8000"  ← REMOVED
    networks:
      - ansible  # ← ADDED
    environment:
      - MODEL=/models/tts.onnx
    volumes:
      - ./models:/models
    # NO TRAEFIK LABELS - configuration is in Ansible project's dynamic.yml
```

**Then add to Ansible project's [`dynamic.yml`](dynamic.yml:1)**:

```yaml
http:
  routers:
    tts:
      rule: "Host(`tts.caronboulme.fr`)"
      entryPoints: [websecure]
      tls:
        certResolver: letsencrypt
      service: tts-service
      middlewares: [vk-hybrid]

  services:
    tts-service:
      loadBalancer:
        servers:
          - url: "http://tts:8000"  # Container name:port
```

**Changes**:
1. ✅ Added external `ansible` network
2. ✅ Connected service to network
3. ❌ Removed port exposure
4. ✅ Added service configuration to Ansible project's [`dynamic.yml`](dynamic.yml:1)

That's it! Your service is now integrated with Ansible proxy with API key authentication and automatic HTTPS.
