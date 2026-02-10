# Guide d'intégration de vos services existants

Ce guide explique comment modifier vos dockers existants (TTS, STT, LLM, Assistant) pour les intégrer au réseau Ansible.

## 🔄 Modifications nécessaires

Vos dockers ont besoin de **très peu de modifications**. Voici exactement ce qu'il faut changer :

### Option 1 : Ajouter au docker-compose.yml principal (RECOMMANDÉ)

Déplacez vos services directement dans [`ansible/docker-compose.yml`](ansible/docker-compose.yml:1).

Remplacez les sections placeholder par vos vraies configurations :

```yaml
# AVANT (placeholder actuel)
tts-service:
  image: your-tts-image:latest
  container_name: ansible-tts
  restart: unless-stopped
  networks:
    - ansible
  environment:
    - TZ=Europe/Paris
  volumes:
    - ./services/tts:/data
  labels:
    - "traefik.enable=true"
    # ... labels Traefik ...

# APRÈS (votre vrai service)
tts-service:
  image: your-actual-tts-image:v1.0  # ← Votre image
  container_name: ansible-tts
  restart: unless-stopped
  networks:
    - ansible  # ← IMPORTANT: doit rester dans le réseau ansible
  environment:
    - TZ=Europe/Paris
    - YOUR_ENV_VAR=value  # ← Vos variables d'environnement
  volumes:
    - ./services/tts:/data  # ← Vos volumes
    - ./config/tts.yml:/app/config.yml  # ← Exemple
  ports: []  # ← VIDER les ports exposés (Traefik gère ça)
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.tts.rule=Host(`tts.mon_url.com`)"
    - "traefik.http.routers.tts.entrypoints=websecure"
    - "traefik.http.routers.tts.tls.certresolver=letsencrypt"
    - "traefik.http.routers.tts.middlewares=vk-tts@docker"
    - "traefik.http.middlewares.vk-tts.forwardauth.address=http://voight-kampff:8080/verify"
    - "traefik.http.middlewares.vk-tts.forwardauth.trustForwardHeader=true"
    - "traefik.http.middlewares.vk-tts.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
    - "traefik.http.services.tts.loadbalancer.server.port=8000"  # ← Port INTERNE de votre app
```

### Option 2 : Garder un docker-compose séparé

Si vous préférez garder vos services dans leur propre `docker-compose.yml` :

#### 2.1 Connecter au réseau externe

Modifiez votre `docker-compose.yml` existant :

```yaml
version: '3.8'

networks:
  ansible:
    external: true  # ← Utilise le réseau créé par ansible/docker-compose.yml
    name: ansible

services:
  tts-service:
    image: your-tts-image:latest
    container_name: my-tts-service
    restart: unless-stopped
    networks:
      - ansible  # ← Connexion au réseau Ansible
    environment:
      - YOUR_ENV_VARS=value
    volumes:
      - ./data:/data
    # IMPORTANT: Ne pas exposer de ports!
    # Traefik gère tout via le réseau interne
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.tts.rule=Host(`tts.mon_url.com`)"
      - "traefik.http.routers.tts.entrypoints=websecure"
      - "traefik.http.routers.tts.tls.certresolver=letsencrypt"
      - "traefik.http.routers.tts.middlewares=vk-tts@docker"
      - "traefik.http.middlewares.vk-tts.forwardauth.address=http://voight-kampff:8080/verify"
      - "traefik.http.middlewares.vk-tts.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.vk-tts.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
      - "traefik.http.services.tts.loadbalancer.server.port=8000"  # Port INTERNE
```

#### 2.2 Démarrage

```bash
# 1. D'abord démarrer Ansible (crée le réseau)
cd ansible
docker-compose up -d

# 2. Puis vos services
cd ../your-service
docker-compose up -d
```

## 📋 Checklist des modifications

Pour **chaque service** (TTS, STT, LLM, Assistant) :

- [ ] Ajouter `networks: - ansible` à votre service
- [ ] Déclarer le réseau `ansible` comme `external: true`
- [ ] **Retirer** tous les `ports:` exposés (sauf si vraiment nécessaire pour du debug)
- [ ] Ajouter les **labels Traefik** pour le routing
- [ ] Adapter `traefik.http.services.XXX.loadbalancer.server.port` au port **interne** de votre app
- [ ] Adapter `Host(...)` avec votre vrai domaine

## 🔧 Labels Traefik à adapter

### Template générique pour n'importe quel service

```yaml
labels:
  # 1. Activer Traefik pour ce service
  - "traefik.enable=true"
  
  # 2. Routing - MODIFIER le host
  - "traefik.http.routers.SERVICE_NAME.rule=Host(`service.mon_url.com`)"
  - "traefik.http.routers.SERVICE_NAME.entrypoints=websecure"
  - "traefik.http.routers.SERVICE_NAME.tls.certresolver=letsencrypt"
  
  # 3. Authentification - MODIFIER le nom du middleware
  - "traefik.http.routers.SERVICE_NAME.middlewares=vk-SERVICE_NAME@docker"
  - "traefik.http.middlewares.vk-SERVICE_NAME.forwardauth.address=http://voight-kampff:8080/verify"
  - "traefik.http.middlewares.vk-SERVICE_NAME.forwardauth.trustForwardHeader=true"
  - "traefik.http.middlewares.vk-SERVICE_NAME.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
  
  # 4. Service - MODIFIER le port interne de votre app
  - "traefik.http.services.SERVICE_NAME.loadbalancer.server.port=8000"
```

**Remplacez** :
- `SERVICE_NAME` → nom unique (tts, stt, llm, assistant, etc.)
- `service.mon_url.com` → votre sous-domaine
- `8000` → le port **interne** sur lequel votre app écoute

## 🔍 Exemples concrets

### Service TTS qui écoute sur le port 5000

```yaml
tts-service:
  image: my-tts:latest
  networks:
    - ansible
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.tts.rule=Host(`tts.mondomaine.fr`)"
    - "traefik.http.routers.tts.entrypoints=websecure"
    - "traefik.http.routers.tts.tls.certresolver=letsencrypt"
    - "traefik.http.routers.tts.middlewares=vk-tts@docker"
    - "traefik.http.middlewares.vk-tts.forwardauth.address=http://voight-kampff:8080/verify"
    - "traefik.http.middlewares.vk-tts.forwardauth.trustForwardHeader=true"
    - "traefik.http.middlewares.vk-tts.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
    - "traefik.http.services.tts.loadbalancer.server.port=5000"  # ← Port interne = 5000
```

### Service sans authentification (comme Immich)

Si vous voulez un service **accessible publiquement sans API key** :

```yaml
public-service:
  image: my-service:latest
  networks:
    - ansible
  labels:
    - "traefik.enable=true"
    - "traefik.http.routers.public.rule=Host(`public.mon_url.com`)"
    - "traefik.http.routers.public.entrypoints=websecure"
    - "traefik.http.routers.public.tls.certresolver=letsencrypt"
    # PAS de middleware d'authentification!
    - "traefik.http.services.public.loadbalancer.server.port=3000"
```

## ⚙️ Configuration de votre application

### Récupérer les headers d'authentification

Voight-Kampff transmet ces headers à votre application après validation :

- `X-VK-User` - Nom de l'utilisateur/clé
- `X-VK-Service` - Service accédé (tts, stt, llm, assistant)
- `X-VK-Scopes` - Liste des scopes autorisés

**Exemple Python (FastAPI/Flask)** :

```python
from fastapi import FastAPI, Header

app = FastAPI()

@app.post("/api/synthesize")
async def synthesize(
    x_vk_user: str = Header(None),
    x_vk_service: str = Header(None),
    x_vk_scopes: str = Header(None)
):
    # Ces headers sont automatiquement fournis par Voight-Kampff
    print(f"Request from user: {x_vk_user}")
    print(f"Service: {x_vk_service}")
    print(f"Allowed scopes: {x_vk_scopes}")
    
    # Votre logique métier
    return {"text": "Hello world"}
```

**Exemple Node.js (Express)** :

```javascript
app.post('/api/synthesize', (req, res) => {
  const user = req.headers['x-vk-user'];
  const service = req.headers['x-vk-service'];
  const scopes = req.headers['x-vk-scopes'];
  
  console.log(`Request from ${user} for ${service}`);
  
  // Votre logique métier
  res.json({ text: 'Hello world' });
});
```

### Pas besoin de vérifier l'API key vous-même !

**Important** : Votre application **n'a pas besoin** de vérifier l'API key. Si la requête arrive à votre service, c'est que Voight-Kampff l'a déjà validée.

Votre app peut juste :
1. Écouter sur son port habituel (ex: 8000, 5000, 3000, etc.)
2. Optionnellement lire les headers `X-VK-*` pour la traçabilité
3. Faire son travail normalement

## 🚨 Erreurs communes

### 1. Service non accessible

**Symptôme** : 404 Not Found ou timeout

**Solutions** :
- Vérifier que le service est dans le réseau `ansible`
- Vérifier le label `traefik.enable=true`
- Vérifier que le port dans `loadbalancer.server.port` correspond au port **interne** de l'app
- Regarder les logs Traefik : `docker-compose logs traefik`

### 2. 401 Unauthorized

**Symptôme** : Requête refusée avec erreur d'authentification

**Solutions** :
- Vérifier que vous utilisez le header `Authorization: Bearer <api_key>`
- Créer une API key avec le bon scope : `./scripts/create-api-key.sh`
- Vérifier que la clé n'est pas expirée : `./scripts/list-api-keys.sh`

### 3. 502 Bad Gateway

**Symptôme** : Traefik ne peut pas joindre le service

**Solutions** :
- Vérifier que le container est démarré : `docker ps`
- Vérifier le port interne : `docker inspect <container>` et chercher "ExposedPorts"
- Vérifier les logs du service : `docker logs <container>`

## 🧪 Tester votre intégration

### 1. Sans authentification (test réseau)

```bash
# Temporairement, retirez le middleware d'authentification de votre service
# et testez juste le routing Traefik

curl https://tts.mon_url.com/health
```

### 2. Avec authentification

```bash
# Créer une API key
./scripts/create-api-key.sh

# Tester
curl https://tts.mon_url.com/api/endpoint \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
```

## 📊 Résumé visuel

```
                    Internet
                       │
                       ▼
                  Port 443 (HTTPS)
                       │
                       ▼
                   Traefik
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    Voight-Kampff   TTS (8000)  STT (5000)
    (vérifie key)   (no ports   (no ports
                     exposed)    exposed)
```

**Points clés** :
- ❌ **Vos services ne doivent PAS exposer de ports** (`ports:` vide ou absent)
- ✅ **Traefik accède aux services via le réseau interne** (ansible)
- ✅ **HTTPS est géré automatiquement** par Traefik
- ✅ **L'authentification est centralisée** dans Voight-Kampff

## 🆘 Besoin d'aide ?

Consultez :
- [`ansible/README.md`](ansible/README.md:1) - Documentation principale
- Logs Traefik : `docker-compose logs -f traefik`
- Logs Voight-Kampff : `docker-compose logs -f voight-kampff`
- Dashboard Traefik : `https://traefik.mon_url.com`
