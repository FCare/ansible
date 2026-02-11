# External Services Integration Guide

This guide explains how to connect your existing services (TTS, STT, LLM, etc.) to the Traefik proxy via the Ansible network.

## 🏗️ Current Architecture

**Important:** This Ansible project is a **Traefik proxy** that routes traffic to **external services**. It only contains Traefik, not the services themselves.

```
Internet → Traefik (Ansible) → External Services (your infrastructure)
```

### Configuration via dynamic.yml

Configuration is done via [`dynamic.yml`](dynamic.yml:1), **not** via docker-compose labels. Here's the current example:

```yaml
# Example configured service
routers:
  thebrain:
    rule: "Host(`thebrain.caronboulme.fr`)"
    entryPoints: [websecure]
    service: vllm-service
    middlewares: [vk-hybrid]

services:
  vllm-service:
    loadBalancer:
      servers:
        - url: "http://qwen-api-server:8000"  # ← External service
```

## 🔄 How to Add Your Service

### 1. Connect your service to the ansible network

Your service must be on the `ansible` network to be accessible by Traefik:

```bash
# If your service is already running
docker network connect ansible your-container

# Or in your docker-compose.yml
networks:
  ansible:
    external: true
    name: ansible

services:
  your-service:
    networks:
      - ansible
    # No need to expose ports!
```

### 2. Configure routing in dynamic.yml

Add your service to [`dynamic.yml`](dynamic.yml:1):

```yaml
http:
  routers:
    # Your new service
    my-service:
      rule: "Host(`my-service.caronboulme.fr`)"  # ← Your subdomain
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt
      service: my-service-backend  # ← Reference to service below
      middlewares:
        - vk-hybrid  # ← Protection by Voight-Kampff

  services:
    # Your service backend
    my-service-backend:
      loadBalancer:
        servers:
          - url: "http://my-container-name:8080"  # ← Container name:port
```

### 3. Test the configuration

```bash
# 1. Restart Traefik to load config
docker-compose restart traefik

# 2. Verify your service is connected to the network
docker network inspect ansible | grep your-service

# 3. Test access
curl -H "Authorization: Bearer YOUR_API_KEY" https://my-service.caronboulme.fr/
```

## 📋 Integration Checklist

For **each service** you want to integrate:

- [ ] Connect service to `ansible` network
- [ ] **Remove** all exposed `ports:` (Traefik handles routing internally)
- [ ] Add router configuration to [`dynamic.yml`](dynamic.yml:1)
- [ ] Add service backend configuration to [`dynamic.yml`](dynamic.yml:1)
- [ ] Update your domain name in the configuration
- [ ] Test the service accessibility

## 🔧 Configuration Templates

### Template for protected service

Add this to [`dynamic.yml`](dynamic.yml:1):

```yaml
http:
  routers:
    my-service:  # ← Unique router name
      rule: "Host(`my-service.caronboulme.fr`)"  # ← Your subdomain
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt
      service: my-service-backend  # ← Reference to service below
      middlewares:
        - vk-hybrid  # ← Hybrid authentication (API + cookies)

  services:
    my-service-backend:  # ← Unique service name
      loadBalancer:
        servers:
          - url: "http://my-container:8080"  # ← Container name and internal port
```

### Template for public service (no authentication)

```yaml
http:
  routers:
    public-service:
      rule: "Host(`public.caronboulme.fr`)"
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt
      service: public-service-backend
      # No middlewares = public access

  services:
    public-service-backend:
      loadBalancer:
        servers:
          - url: "http://public-container:3000"
```

## 🔍 Real Examples

### Current TTS Service (Unmute Talk)

```yaml
unmute-talk:
  rule: "Host(`unmute-talk.caronboulme.fr`)"
  entryPoints: [websecure]
  tls:
    certResolver: letsencrypt
  service: tts-service
  middlewares: [vk-hybrid]

# Service backend
tts-service:
  loadBalancer:
    servers:
      - url: "http://tts:8080"  # Container 'tts' on port 8080
```

### Current Photos Service (No Auth)

```yaml
photos:
  rule: "Host(`photos.caronboulme.fr`)"
  entryPoints: [websecure]
  tls:
    certResolver: letsencrypt
  service: photos-service
  # No middlewares - public access, Immich has its own auth

# Service backend
photos-service:
  loadBalancer:
    servers:
      - url: "http://immich_server:2283"  # Immich container on port 2283
```

## ⚙️ Application Configuration

### Authentication Headers

Voight-Kampff forwards these headers to your application after validation:

- `X-VK-User` - User/key name
- `X-VK-Service` - Service being accessed (tts, stt, llm, assistant)
- `X-VK-Scopes` - List of allowed scopes
- `X-VK-Admin` - Admin status (for admin-required services like Traefik dashboard)

**Python Example (FastAPI/Flask)**:

```python
from fastapi import FastAPI, Header

app = FastAPI()

@app.post("/api/synthesize")
async def synthesize(
    x_vk_user: str = Header(None),
    x_vk_service: str = Header(None),
    x_vk_scopes: str = Header(None),
    x_vk_admin: str = Header(None)
):
    # Headers automatically provided by Voight-Kampff
    print(f"Request from user: {x_vk_user}")
    print(f"Service: {x_vk_service}")
    print(f"Allowed scopes: {x_vk_scopes}")
    print(f"Admin access: {x_vk_admin}")
    
    # Your business logic
    return {"text": "Hello world"}
```

**Node.js Example (Express)**:

```javascript
app.post('/api/synthesize', (req, res) => {
  const user = req.headers['x-vk-user'];
  const service = req.headers['x-vk-service'];
  const scopes = req.headers['x-vk-scopes'];
  const admin = req.headers['x-vk-admin'];
  
  console.log(`Request from ${user} for ${service}`);
  
  // Your business logic
  res.json({ text: 'Hello world' });
});
```

### No Need to Verify API Keys Yourself!

**Important**: Your application **doesn't need** to verify API keys. If the request reaches your service, Voight-Kampff has already validated it.

Your app just needs to:
1. Listen on its usual port (e.g., 8000, 5000, 3000, etc.)
2. Optionally read `X-VK-*` headers for logging/tracing
3. Do its work normally

## 🚨 Common Issues

### 1. Service Not Accessible

**Symptom**: 404 Not Found or timeout

**Solutions**:
- Verify service is connected to `ansible` network
- Check router configuration in [`dynamic.yml`](dynamic.yml:1)
- Verify the URL in service backend matches container name and port
- Check Traefik logs: `docker-compose logs traefik`

### 2. 401 Unauthorized

**Symptom**: Request denied with authentication error

**Solutions**:
- Verify you're using the `Authorization: Bearer <api_key>` header
- Check API key is valid and not expired in Voight-Kampff
- Ensure service has the `vk-hybrid` middleware configured

### 3. 502 Bad Gateway

**Symptom**: Traefik cannot reach the service

**Solutions**:
- Verify container is running: `docker ps`
- Check container is on ansible network: `docker network inspect ansible`
- Verify internal port in service backend configuration
- Check service logs: `docker logs <container>`

## 🧪 Testing Your Integration

### 1. Test Network Connectivity

```bash
# Test from within the ansible network
docker run --rm --network ansible alpine/curl \
  curl http://your-container:8080/health
```

### 2. Test via Traefik (with authentication)

```bash
# Test with API key
curl https://your-service.caronboulme.fr/health \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json"
```

### 3. Test Configuration Syntax

```bash
# Validate dynamic.yml syntax
docker-compose config
```

## 📊 Visual Architecture

```
                    Internet
                       │
                       ▼
                  Port 443 (HTTPS)
                       │
                       ▼
                   Traefik
                 (Ansible Project)
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    Voight-Kampff   Your External Services
    (auth service)   (connected to network)
                     (no ports exposed)
```

**Key Points**:
- ❌ **External services should NOT expose ports** (`ports:` empty or absent)
- ✅ **Traefik accesses services via internal network** (ansible)
- ✅ **HTTPS is handled automatically** by Traefik
- ✅ **Authentication is centralized** in Voight-Kampff
- ✅ **Configuration via [`dynamic.yml`](dynamic.yml:1)**, not docker labels

## 🆘 Need Help?

Check:
- [`README.md`](README.md:1) - Main documentation
- Traefik logs: `docker-compose logs -f traefik`
- Network inspection: `docker network inspect ansible`
- Traefik dashboard: `https://traefik.caronboulme.fr` (admin access required)
- Current service configurations in [`dynamic.yml`](dynamic.yml:1)
