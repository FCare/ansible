# Option 2 : Garder vos docker-compose séparés

Ce guide détaille comment intégrer vos services existants au réseau Ansible **en gardant vos fichiers docker-compose séparés**.

Cette option est idéale si :
- ✅ Vous avez déjà des docker-compose bien organisés
- ✅ Vous voulez gérer vos services indépendamment
- ✅ Vous développez/testez vos services séparément
- ✅ Vous avez des configurations complexes à préserver

## 📁 Structure de répertoires recommandée

```
/home/user/
├── ansible/                    # Le déploiement Traefik
│   ├── docker-compose.yml
│   ├── traefik/
│   └── voight-kampff/
├── services/
│   ├── tts/                   # Votre service TTS
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   └── src/
│   ├── stt/                   # Votre service STT
│   │   ├── docker-compose.yml
│   │   ├── Dockerfile
│   │   └── src/
│   ├── llm/                   # Votre service LLM
│   │   ├── docker-compose.yml
│   │   └── models/
│   └── assistant/             # Votre assistant backend
│       ├── docker-compose.yml
│       └── src/
```

## 🔧 Étape 1 : Modifier vos docker-compose existants

### Exemple complet pour le service TTS

**Fichier : `/home/user/services/tts/docker-compose.yml`**

```yaml
version: '3.8'

# IMPORTANT: Déclarer le réseau ansible comme externe
networks:
  ansible:
    external: true
    name: ansible

services:
  tts:
    build: .
    # OU : image: your-tts-image:latest
    container_name: tts-service
    restart: unless-stopped
    
    # ⚠️ IMPORTANT: Connecter au réseau ansible
    networks:
      - ansible
    
    # ❌ NE PAS exposer de ports (Traefik gère tout)
    # ports:
    #   - "8000:8000"  # ← À SUPPRIMER
    
    environment:
      - TTS_MODEL=/models/tts.onnx
      - TTS_VOICE=fr-FR
      - LOG_LEVEL=info
    
    volumes:
      - ./models:/models
      - ./cache:/cache
      - ./config.yml:/app/config.yml
    
    # ✅ Labels Traefik pour le routing et l'authentification
    labels:
      # Activer Traefik
      - "traefik.enable=true"
      
      # Routing HTTPS
      - "traefik.http.routers.tts.rule=Host(`tts.mon_url.com`)"
      - "traefik.http.routers.tts.entrypoints=websecure"
      - "traefik.http.routers.tts.tls.certresolver=letsencrypt"
      
      # Authentification par Voight-Kampff
      - "traefik.http.routers.tts.middlewares=vk-tts@docker"
      - "traefik.http.middlewares.vk-tts.forwardauth.address=http://voight-kampff:8080/verify"
      - "traefik.http.middlewares.vk-tts.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.vk-tts.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
      
      # Port interne de l'application (adapter selon votre app)
      - "traefik.http.services.tts.loadbalancer.server.port=8000"
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Exemple pour le service STT

**Fichier : `/home/user/services/stt/docker-compose.yml`**

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
      - STT_LANGUAGE=fr
      - CUDA_VISIBLE_DEVICES=0  # Si vous utilisez GPU
    
    volumes:
      - ./models:/models
      - ./audio:/audio
    
    # Montage GPU (si nécessaire)
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.stt.rule=Host(`stt.mon_url.com`)"
      - "traefik.http.routers.stt.entrypoints=websecure"
      - "traefik.http.routers.stt.tls.certresolver=letsencrypt"
      - "traefik.http.routers.stt.middlewares=vk-stt@docker"
      - "traefik.http.middlewares.vk-stt.forwardauth.address=http://voight-kampff:8080/verify"
      - "traefik.http.middlewares.vk-stt.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.vk-stt.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
      - "traefik.http.services.stt.loadbalancer.server.port=5000"  # Port interne
```

### Exemple pour le service LLM

**Fichier : `/home/user/services/llm/docker-compose.yml`**

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible

services:
  llm:
    image: ollama/ollama:latest
    # OU votre propre image
    container_name: llm-service
    restart: unless-stopped
    networks:
      - ansible
    
    environment:
      - OLLAMA_MODELS=/models
      - OLLAMA_HOST=0.0.0.0:11434
    
    volumes:
      - ./models:/models
      - ./cache:/root/.ollama
    
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.llm.rule=Host(`llm.mon_url.com`)"
      - "traefik.http.routers.llm.entrypoints=websecure"
      - "traefik.http.routers.llm.tls.certresolver=letsencrypt"
      - "traefik.http.routers.llm.middlewares=vk-llm@docker"
      - "traefik.http.middlewares.vk-llm.forwardauth.address=http://voight-kampff:8080/verify"
      - "traefik.http.middlewares.vk-llm.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.vk-llm.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
      - "traefik.http.services.llm.loadbalancer.server.port=11434"
```

### Exemple pour l'Assistant Backend

**Fichier : `/home/user/services/assistant/docker-compose.yml`**

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible
  
  # Réseau interne pour la base de données (optionnel)
  assistant-internal:
    driver: bridge

services:
  assistant-api:
    build: ./backend
    container_name: assistant-api
    restart: unless-stopped
    networks:
      - ansible           # Pour Traefik
      - assistant-internal  # Pour la DB
    
    environment:
      - DATABASE_URL=postgresql://user:pass@assistant-db:5432/assistant
      - REDIS_URL=redis://assistant-redis:6379
      - SECRET_KEY=${SECRET_KEY}
    
    volumes:
      - ./backend/src:/app/src
      - ./data:/data
    
    depends_on:
      - assistant-db
      - assistant-redis
    
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.assistant.rule=Host(`assistant.mon_url.com`)"
      - "traefik.http.routers.assistant.entrypoints=websecure"
      - "traefik.http.routers.assistant.tls.certresolver=letsencrypt"
      - "traefik.http.routers.assistant.middlewares=vk-assistant@docker"
      - "traefik.http.middlewares.vk-assistant.forwardauth.address=http://voight-kampff:8080/verify"
      - "traefik.http.middlewares.vk-assistant.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.vk-assistant.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
      - "traefik.http.services.assistant.loadbalancer.server.port=8080"
  
  # Base de données (pas exposée via Traefik)
  assistant-db:
    image: postgres:16
    container_name: assistant-db
    restart: unless-stopped
    networks:
      - assistant-internal  # SEULEMENT le réseau interne
    
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=assistant
    
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
  
  # Redis (pas exposé via Traefik)
  assistant-redis:
    image: redis:alpine
    container_name: assistant-redis
    restart: unless-stopped
    networks:
      - assistant-internal
```

## 🚀 Étape 2 : Démarrage des services

### Ordre de démarrage IMPORTANT

```bash
# 1. D'abord démarrer Ansible (crée le réseau et Traefik)
cd /home/user/ansible
docker-compose up -d

# Attendre que Traefik soit prêt
docker-compose logs -f traefik
# Attendre de voir "Configuration loaded"

# 2. Ensuite démarrer vos services dans n'importe quel ordre
cd /home/user/services/tts
docker-compose up -d

cd /home/user/services/stt
docker-compose up -d

cd /home/user/services/llm
docker-compose up -d

cd /home/user/services/assistant
docker-compose up -d
```

### Script de démarrage automatique

Créez `/home/user/start-all.sh` :

```bash
#!/bin/bash
set -e

echo "🚀 Démarrage de l'infrastructure Ansible..."

# 1. Ansible (Traefik + Voight-Kampff)
cd /home/user/ansible
docker-compose up -d
echo "✅ Ansible démarré"

# Attendre que Traefik soit prêt
echo "⏳ Attente de Traefik..."
sleep 5

# 2. Services
echo "🚀 Démarrage des services..."

cd /home/user/services/tts
docker-compose up -d
echo "✅ TTS démarré"

cd /home/user/services/stt
docker-compose up -d
echo "✅ STT démarré"

cd /home/user/services/llm
docker-compose up -d
echo "✅ LLM démarré"

cd /home/user/services/assistant
docker-compose up -d
echo "✅ Assistant démarré"

echo ""
echo "✅ Tous les services sont démarrés!"
echo ""
echo "Services disponibles:"
echo "  - https://traefik.mon_url.com (Dashboard Traefik)"
echo "  - https://auth.mon_url.com (Voight-Kampff)"
echo "  - https://tts.mon_url.com"
echo "  - https://stt.mon_url.com"
echo "  - https://llm.mon_url.com"
echo "  - https://assistant.mon_url.com"
echo ""
echo "Créer une API key:"
echo "  cd /home/user/ansible && ./scripts/create-api-key.sh"
```

Rendez-le exécutable :

```bash
chmod +x /home/user/start-all.sh
```

## 🛑 Arrêt des services

### Script d'arrêt

Créez `/home/user/stop-all.sh` :

```bash
#!/bin/bash
set -e

echo "🛑 Arrêt des services..."

cd /home/user/services/assistant
docker-compose down
echo "✅ Assistant arrêté"

cd /home/user/services/llm
docker-compose down
echo "✅ LLM arrêté"

cd /home/user/services/stt
docker-compose down
echo "✅ STT arrêté"

cd /home/user/services/tts
docker-compose down
echo "✅ TTS arrêté"

cd /home/user/ansible
docker-compose down
echo "✅ Ansible arrêté"

echo ""
echo "✅ Tous les services sont arrêtés"
```

## 🔄 Redémarrer un service spécifique

```bash
# Redémarrer juste le service TTS
cd /home/user/services/tts
docker-compose restart

# Ou rebuild et redémarrer
docker-compose up -d --build
```

## 🐛 Debug et logs

### Voir les logs d'un service

```bash
cd /home/user/services/tts
docker-compose logs -f

# Ou directement
docker logs -f tts-service
```

### Vérifier la connexion au réseau

```bash
# Lister les containers sur le réseau ansible
docker network inspect ansible

# Devrait montrer:
# - ansible-traefik
# - ansible-voight-kampff
# - tts-service
# - stt-service
# - llm-service
# - assistant-api
```

### Tester depuis un container

```bash
# Entrer dans un container
docker exec -it tts-service sh

# Tester la connexion à Voight-Kampff
curl http://voight-kampff:8080/health
# Devrait retourner: {"status":"operational","test":"positive"}

# Tester les autres services
curl http://stt:5000/health
curl http://llm:11434/health
```

## 🔐 Gestion des secrets

### Utiliser .env par service

**`/home/user/services/tts/.env`**
```env
TTS_MODEL=tts-v2.onnx
TTS_API_KEY=local-only-not-for-external
LOG_LEVEL=debug
```

**`/home/user/services/tts/docker-compose.yml`**
```yaml
services:
  tts:
    env_file:
      - .env  # ← Charge automatiquement les variables
```

### Centraliser les secrets (optionnel)

Créez `/home/user/.env` avec tous vos secrets :

```env
# TTS
TTS_MODEL=tts-v2.onnx

# STT
STT_MODEL=whisper-large-v3

# LLM
LLM_MODEL=llama3:70b

# Assistant
ASSISTANT_SECRET_KEY=super-secret-key-here
DATABASE_PASSWORD=postgres-password-here
```

Référencez-le dans chaque docker-compose :

```yaml
services:
  tts:
    env_file:
      - ../../.env  # Chemin relatif vers le .env central
```

## 📊 Monitoring centralisé

### Voir tous les services d'un coup

```bash
# Status de tous les containers
docker ps --filter "network=ansible" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Logs de tous les services
docker-compose -f /home/user/ansible/docker-compose.yml logs -f &
docker-compose -f /home/user/services/tts/docker-compose.yml logs -f &
docker-compose -f /home/user/services/stt/docker-compose.yml logs -f &
docker-compose -f /home/user/services/llm/docker-compose.yml logs -f &
docker-compose -f /home/user/services/assistant/docker-compose.yml logs -f
```

### Dashboard Traefik

Accédez à `https://traefik.mon_url.com` pour voir :
- ✅ État de tous les services
- ✅ Routes configurées
- ✅ Certificats SSL
- ✅ Middlewares actifs

## 🔄 Mise à jour d'un service

```bash
# 1. Aller dans le répertoire du service
cd /home/user/services/tts

# 2. Arrêter le service
docker-compose down

# 3. Mettre à jour l'image (si externe)
docker-compose pull

# 4. Ou rebuild (si build local)
docker-compose build

# 5. Redémarrer
docker-compose up -d

# 6. Vérifier les logs
docker-compose logs -f
```

## ✅ Checklist de migration

Pour chaque service existant :

- [ ] Ajouter `networks: ansible: external: true` en haut du docker-compose
- [ ] Ajouter `networks: - ansible` au service
- [ ] **Supprimer** ou commenter tous les `ports:` exposés
- [ ] Ajouter les **labels Traefik** (copier le template)
- [ ] Adapter `loadbalancer.server.port` au port **interne** de votre app
- [ ] Adapter `Host(...)` avec votre sous-domaine réel
- [ ] Tester : `docker-compose config` (vérifie la syntaxe)
- [ ] Démarrer : `docker-compose up -d`
- [ ] Vérifier : `docker-compose logs -f`
- [ ] Tester l'accès : `curl https://service.mon_url.com/health -H "Authorization: Bearer API_KEY"`

## 🆘 Problèmes courants

### "network ansible not found"

**Cause** : Ansible n'est pas démarré ou le réseau n'existe pas

**Solution** :
```bash
cd /home/user/ansible
docker-compose up -d
```

### "Container cannot connect to voight-kampff"

**Cause** : Le service n'est pas sur le réseau ansible

**Solution** : Vérifier que `networks: - ansible` est bien présent dans le service

### Service accessible sans API key

**Cause** : Le middleware d'authentification n'est pas appliqué

**Solution** : Vérifier que le label `traefik.http.routers.XXX.middlewares=vk-XXX@docker` est présent

## 📝 Exemple de migration complète

### Avant (votre docker-compose existant)

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

### Après (intégré à Ansible)

```yaml
version: '3.8'

networks:
  ansible:
    external: true
    name: ansible

services:
  tts:
    build: .
    # ports: - "8000:8000"  ← SUPPRIMÉ
    networks:
      - ansible  # ← AJOUTÉ
    environment:
      - MODEL=/models/tts.onnx
    volumes:
      - ./models:/models
    labels:  # ← AJOUTÉ
      - "traefik.enable=true"
      - "traefik.http.routers.tts.rule=Host(`tts.mon_url.com`)"
      - "traefik.http.routers.tts.entrypoints=websecure"
      - "traefik.http.routers.tts.tls.certresolver=letsencrypt"
      - "traefik.http.routers.tts.middlewares=vk-tts@docker"
      - "traefik.http.middlewares.vk-tts.forwardauth.address=http://voight-kampff:8080/verify"
      - "traefik.http.middlewares.vk-tts.forwardauth.trustForwardHeader=true"
      - "traefik.http.middlewares.vk-tts.forwardauth.authResponseHeaders=X-VK-User,X-VK-Service,X-VK-Scopes"
      - "traefik.http.services.tts.loadbalancer.server.port=8000"
```

**Modifications** :
1. ✅ Ajout du réseau externe `ansible`
2. ✅ Connexion du service au réseau
3. ❌ Suppression de l'exposition des ports
4. ✅ Ajout des labels Traefik

C'est tout ! Votre service est maintenant intégré à Ansible avec authentification par API key et HTTPS automatique.
