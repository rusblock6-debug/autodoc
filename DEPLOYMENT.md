# AutoDoc AI System - Deployment Guide

## 🎯 System Overview

AutoDoc AI is a complete platform for automated guide creation that combines screen recording, AI processing, and content generation. It replicates functionality similar to Guidde.com with full offline/local AI capabilities.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AutoDoc AI System                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌────────────────────┐  │
│  │ Chrome Ext  │  │  Frontend   │  │    FastAPI         │  │
│  │ (Recorder)  │  │   React     │  │    Backend         │  │
│  └─────────────┘  └─────────────┘  └────────────────────┘  │
│         │                 │                   │             │
│         └─────────────────┴───────────────────┘             │
│                           │                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    Services Layer                     │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐│  │
│  │  │  Whisper │  │   LLM    │  │   TTS    │  │Video   ││  │
│  │  │   ASR    │  │  Qwen    │  │  Edge    │  │Engine  ││  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘│  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                 │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                   Infrastructure                      │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐│  │
│  │  │PostgreSQL│  │  Redis   │  │  MinIO   │  │Celery  ││  │
│  │  │ Database │  │  Queue   │  │ Storage  │  │Workers ││  │
│  │  └──────────┘  └──────────┘  └──────────┘  └────────┘│  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start (Development)

### Prerequisites
- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.10+ (for local development)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd autodoc
cp .env.example .env
```

### 2. Configure Environment Variables

Edit `.env` file:

```bash
# Database
POSTGRES_USER=autodoc
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=autodoc

# Redis
REDIS_PASSWORD=redis_password

# MinIO
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin123

# AI Models
WHISPER_MODEL_SIZE=medium  # or large for better accuracy
WHISPER_DEVICE=cuda        # or cpu for CPU-only systems

# LLM (if using local models)
LLM_MODEL_PATH=/models/qwen2.5-7b.gguf
```

### 3. Start Development Environment

```bash
# Build and start all services
docker-compose up --build

# Or start in detached mode
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Access Services

- **Frontend**: http://localhost:3000
- **Backend API Docs**: http://localhost:8000/docs
- **MinIO Console**: http://localhost:9001 (admin/minioadmin123)
- **Redis Commander**: http://localhost:8081

## 🛠️ Development Setup

### Backend Development

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Frontend Development

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### Chrome Extension Development

1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode"
3. Click "Load unpacked" and select the `extension` folder
4. Pin the extension for easy access

## 📦 Production Deployment

### Option 1: Docker Compose (Recommended)

```bash
# Production-ready compose file
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=3
```

### Option 2: Manual Installation

#### Server Requirements
- Ubuntu 20.04+ or CentOS 8+
- 16GB RAM minimum (32GB recommended)
- NVIDIA GPU with 8GB+ VRAM (optional but recommended)
- 100GB+ storage

#### Installation Steps

```bash
# 1. Install system dependencies
sudo apt update
sudo apt install -y python3-pip python3-dev nginx docker.io docker-compose

# 2. Install NVIDIA drivers (if using GPU)
sudo apt install -y nvidia-driver-535 nvidia-cuda-toolkit

# 3. Clone repository
git clone <repo-url> /opt/autodoc
cd /opt/autodoc

# 4. Set up systemd services
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 5. Start services
sudo systemctl enable autodoc-backend
sudo systemctl start autodoc-backend
```

## 🔧 Configuration

### AI Model Selection

Choose models based on your hardware:

**For 16GB RAM systems:**
```bash
WHISPER_MODEL_SIZE=medium
LLM_MODEL=qwen2.5-7b  # Requires ~8GB VRAM
```

**For 32GB+ RAM systems:**
```bash
WHISPER_MODEL_SIZE=large
LLM_MODEL=qwen2.5-72b # Requires ~20GB VRAM
```

### Performance Tuning

```bash
# Adjust worker concurrency
CELERY_WORKER_CONCURRENCY=2

# Limit GPU memory
CUDA_VISIBLE_DEVICES=0
```

## 🔄 CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy AutoDoc AI

on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker images
        run: |
          docker build -t autodoc-backend:${{ github.sha }} ./app
          docker build -t autodoc-frontend:${{ github.sha }} ./frontend
          
      - name: Push to registry
        run: |
          docker push autodoc-backend:${{ github.sha }}
          docker push autodoc-frontend:${{ github.sha }}
          
      - name: Deploy to production
        run: |
          ssh deploy@server "cd /opt/autodoc && docker-compose pull && docker-compose up -d"
```

## 📊 Monitoring

### Health Checks

```bash
# Check system health
curl http://localhost:8000/health

# Check individual services
docker-compose ps
```

### Logs Management

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f backend
docker-compose logs -f worker
```

## 🔒 Security

### SSL/TLS Setup

```nginx
# nginx/sites-available/autodoc
server {
    listen 443 ssl http2;
    server_name autodoc.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
    }
}
```

### Authentication

The system includes JWT-based authentication. Configure in `.env`:

```bash
JWT_SECRET_KEY=your-super-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
```

## 🆘 Troubleshooting

### Common Issues

**GPU not detected:**
```bash
# Check NVIDIA drivers
nvidia-smi

# Install nvidia-container-toolkit
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

**Models not downloading:**
```bash
# Manually download models
mkdir -p /models
wget -O /models/whisper-medium.pt https://openaipublic.azureedge.net/main/whisper/models/...
```

**Permission errors:**
```bash
# Fix file permissions
sudo chown -R $(whoami) /opt/autodoc
sudo chmod -R 755 /opt/autodoc
```

## 📈 Scaling

### Horizontal Scaling

```bash
# Scale backend workers
docker-compose up -d --scale worker=4

# Load balancing with nginx
upstream backend_workers {
    server worker1:8000;
    server worker2:8000;
    server worker3:8000;
}
```

## 🎯 Usage Workflow

1. **Install Chrome Extension** - Record screen interactions
2. **Upload Recording** - Through web interface or extension
3. **AI Processing** - Automatic transcription and step detection
4. **Edit Guide** - Refine steps and adjust markers
5. **Export Content** - Generate Markdown/HTML guides
6. **Create Shorts** - Generate vertical videos with voiceover

## 🤝 Support

For issues and questions:
- GitHub Issues: [Repository Issues](https://github.com/your-repo/issues)
- Documentation: [Wiki](https://github.com/your-repo/wiki)
- Contact: support@autodoc.ai

---

**Happy documenting! 📝**