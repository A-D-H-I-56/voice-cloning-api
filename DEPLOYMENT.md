# Production Deployment Guide

## 🔐 Security Checklist

### Before Deployment:

- [ ] **Generate a strong API key:**

  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(32))"
  ```

  Set this in your `.env` file as `API_KEY`

- [ ] **MongoDB Atlas Setup:**
  - You have a MongoDB Atlas cluster at: `ac-fonpuip-shard-00-*.oukn5n5.mongodb.net`
  - Verify credentials are correct in `.env` → `MONGO_URI`
  - **DO NOT** commit `.env` to git

- [ ] **Verify .env is NOT in git:**

  ```bash
  git status
  # Should show .env in gitignore (not in staging)
  ```

- [ ] **Remove .env from git history (if previously committed):**
  ```bash
  # ⚠️ This rewrites all history - coordinate with team first
  git filter-branch --tree-filter 'rm -f .env' HEAD
  git push --force-with-lease
  ```

---

## 🚀 Local Development

### 1. Setup

```bash
# Clone and setup
git clone <repo>
cd voice-cloning-api

# Copy environment template
cp .env.example .env

# Edit .env with your settings
# vi .env

# Install dependencies
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

pip install -r requirements.txt
```

### 2. Run with Docker Compose

```bash
# Build and start all services
docker compose up --build

# On first run, the model will download (~2-3 minutes)
# Monitor with:
docker compose logs -f api

# Test the API
curl http://localhost:8000/health
```

### 3. Test Authentication

```bash
# Get API key from .env
API_KEY=$(grep "API_KEY=" .env | cut -d'=' -f2)

# Try without auth (should fail)
curl -X GET http://localhost:8000/clones

# Try with auth (should work)
curl -X GET http://localhost:8000/clones \
  -H "Authorization: Bearer $API_KEY"
```

---

## 📦 Docker Deployment

### Build Image

```bash
docker build -t voice-cloning-api:1.0.0 .
docker tag voice-cloning-api:1.0.0 voice-cloning-api:latest
```

### Environment Variables for Production

```bash
export MONGO_URI="mongodb+srv://Adhi:Adnan998877@ac-fonpuip-shard-00-*.oukn5n5.mongodb.net/voice-cloning?..."
export API_KEY="your-strong-key-here"
export DEBUG="false"

docker run -d \
  --name voice-cloning-api \
  -p 8000:8000 \
  -e MONGO_URI="$MONGO_URI" \
  -e API_KEY="$API_KEY" \
  -e DEBUG="false" \
  -v $(pwd)/checkpoints:/app/checkpoints \
  -v $(pwd)/outputs:/app/outputs \
  voice-cloning-api:latest
```

---

## ☁️ Kubernetes Deployment (Recommended for Production)

### 1. Create secrets

```bash
kubectl create secret generic voice-cloning-secrets \
  --from-literal=mongo-uri="mongodb+srv://..." \
  --from-literal=api-key="your-secret-key"
```

### 2. Deploy with ConfigMap + Secret

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: voice-cloning-config
data:
  DEBUG: "false"
  DB_NAME: "voice-cloning"
  COQUI_TOS_AGREED: "1"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-cloning-api
spec:
  replicas: 1 # Keep at 1 due to GPU memory constraints
  selector:
    matchLabels:
      app: voice-cloning-api
  template:
    metadata:
      labels:
        app: voice-cloning-api
    spec:
      containers:
        - name: api
          image: voice-cloning-api:1.0.0
          ports:
            - containerPort: 8000
          env:
            - name: MONGO_URI
              valueFrom:
                secretKeyRef:
                  name: voice-cloning-secrets
                  key: mongo-uri
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: voice-cloning-secrets
                  key: api-key
          envFrom:
            - configMapRef:
                name: voice-cloning-config
          resources:
            requests:
              memory: "4Gi"
              cpu: "2"
            limits:
              memory: "8Gi"
              cpu: "4"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          volumeMounts:
            - name: checkpoints
              mountPath: /app/checkpoints
            - name: outputs
              mountPath: /app/outputs
      volumes:
        - name: checkpoints
          persistentVolumeClaim:
            claimName: checkpoints-pvc
        - name: outputs
          persistentVolumeClaim:
            claimName: outputs-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: voice-cloning-api-service
spec:
  type: LoadBalancer
  selector:
    app: voice-cloning-api
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
```

---

## 🔄 MongoDB Atlas Maintenance

### Backup

- Enable automated backups in MongoDB Atlas dashboard
- Set retention to 30 days minimum

### Monitoring

- Enable monitoring in MongoDB Atlas
- Set alerts for:
  - Connection count spikes
  - Query performance degradation
  - Disk usage > 80%

---

## 📊 Monitoring & Logging

### Recommended Setup

1. **Logging**: Send docker logs to centralized service (ELK, DataDog, etc.)
2. **Metrics**: Export prometheus metrics
3. **Alerts**: Alert on:
   - 5xx error rate > 1%
   - API latency p95 > 10s
   - Disk usage > 80%
   - Database connection failures

### View Logs

```bash
# Docker Compose
docker compose logs -f api

# Docker container
docker logs -f voice_cloning_api

# Kubernetes
kubectl logs -f deployment/voice-cloning-api
```

---

## 🛡️ Security Best Practices

✅ **Done in this update:**

- [x] API key authentication on all endpoints
- [x] Rate limiting (10 req/min per IP)
- [x] File upload size limits (50 MB)
- [x] Input validation (clone_id, file types)
- [x] Path traversal prevention
- [x] Graceful shutdown handling
- [x] Proper error handling and rollback

⚠️ **Still needed:**

- [ ] HTTPS/TLS in production
- [ ] WAF (Web Application Firewall)
- [ ] Request logging & audit trails
- [ ] Database encryption at rest
- [ ] Secrets rotation policy
- [ ] Regular security audits

---

## 🔧 Troubleshooting

### API won't start

```bash
# Check logs
docker compose logs api

# Common issues:
# 1. API_KEY not set: Set valid API_KEY in .env
# 2. MongoDB connection failed: Check MONGO_URI
# 3. Model download failed: Check disk space (~5GB needed)
```

### Model download stuck

```bash
# The model cache is in a docker volume
# Clear and retry:
docker volume rm voice-cloning-api_tts_model_cache
docker compose up --build api
```

### High latency on first request

- First inference caches the model in GPU memory
- This is expected, takes 2-5 seconds
- Subsequent requests are faster (~1-2 seconds)

---

## 📈 Performance Tuning

### Single Worker Design (Intentional)

- Running multiple Uvicorn workers would create multiple copies of the 2.2GB model
- We use single worker + thread pool instead
- Scale horizontally by running multiple containers (with load balancer)

### GPU Acceleration

To enable NVIDIA GPU:

1. Install nvidia-container-toolkit
2. Update docker-compose.yml GPU section
3. Change PyTorch index in Dockerfile to CUDA
4. Rebuild: `docker compose up --build`

---

## 📝 API Usage Example

```bash
# Set your API key
API_KEY="your-api-key-from-.env"

# 1. Create a voice clone
curl -X POST http://localhost:8000/clone \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@sample_voice.wav"

# Response:
# {
#   "clone_id": "6651a3f4e4b0f1c2d3e4f5a6",
#   "original_filename": "sample_voice.wav",
#   "embedding_path": "checkpoints/6651a3f4e4b0f1c2d3e4f5a6.pt",
#   "created_at": "2025-01-15T10:30:00Z"
# }

# 2. Synthesize speech
curl -X POST http://localhost:8000/speak \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "clone_id": "6651a3f4e4b0f1c2d3e4f5a6",
    "text": "Hello, this is my cloned voice!",
    "language": "en"
  }' \
  --output output.wav

# 3. List clones
curl -X GET http://localhost:8000/clones \
  -H "Authorization: Bearer $API_KEY"

# 4. Delete a clone
curl -X DELETE http://localhost:8000/clone/6651a3f4e4b0f1c2d3e4f5a6 \
  -H "Authorization: Bearer $API_KEY"
```

---

**Last Updated:** 2026-04-12  
**Status:** Production Ready (Tier 1 fixes applied)
