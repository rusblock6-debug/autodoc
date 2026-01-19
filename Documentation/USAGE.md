# AutoDoc AI System - Usage Guide

## 🚀 Getting Started

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/your-org/autodoc.git
cd autodoc

# Copy environment configuration
cp .env.example .env

# Start the system
docker-compose up -d
```

### 2. Install Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable "Developer mode" (toggle in top right)
3. Click "Load unpacked" and select the `extension` folder
4. Pin the extension for easy access

## 🎯 Creating Your First Guide

### Method 1: Using Chrome Extension (Recommended)

1. **Start Recording**
   - Click the AutoDoc extension icon
   - Click "Start Recording"
   - Perform actions on the screen while explaining aloud
   - Click "Stop Recording" when finished

2. **Automatic Processing**
   - The system automatically:
     - Transcribes your speech using Whisper
     - Detects clicks and creates steps
     - Extracts screenshots at click moments
     - Normalizes instructions using LLM

3. **Edit and Refine**
   - Visit http://localhost:3000
   - Find your new guide in "My Guides"
   - Click "Edit" to refine:
     - Adjust text instructions
     - Move click markers to correct positions
     - Reorder or delete steps

4. **Export Content**
   - Choose "Export" to generate:
     - Markdown documentation
     - HTML guide with embedded images
   - Or choose "Generate Shorts" for video content

### Method 2: Manual Upload

1. **Create Empty Guide**
   - Go to http://localhost:3000/guides/create
   - Enter guide title and description
   - Skip file upload for now

2. **Upload Recording Later**
   - In the editor, use the upload section
   - Drag & drop your screen recording
   - System processes automatically

## 🛠️ Interface Walkthrough

### Dashboard (http://localhost:3000)
- **My Guides**: Browse all created guides
- **Create New**: Start fresh or upload recordings
- **Search**: Filter guides by title or content

### Guide Editor
- **Left Panel**: Interactive preview with draggable markers
- **Right Panel**: Editable step cards with:
  - Step number and text
  - Edit button for text refinement
  - Reorder arrows (↑↓)
  - Delete option (🗑️)

### Export Options
- **Markdown**: Clean documentation format
- **HTML**: Rich format with embedded screenshots
- **Preview**: See exactly how exports will look

### Shorts Generator
- **Voice Selection**: Choose narrator voice
- **Progress Tracking**: Real-time generation status
- **Video Preview**: Watch before downloading
- **Quality Options**: Select output resolution

## 🔧 Advanced Features

### Custom Voice Configuration

Edit `.env` to add custom voices:
```bash
# Russian voices
TTS_VOICE_RU_FEMALE=ru-RU-SvetlanaNeural
TTS_VOICE_RU_MALE=ru-RU-DmitryNeural

# English voices  
TTS_VOICE_EN_FEMALE=en-US-JennyNeural
TTS_VOICE_EN_MALE=en-US-GuyNeural
```

### Model Optimization

For better performance:
```bash
# Use smaller models for faster processing
WHISPER_MODEL_SIZE=small  # Instead of medium/large

# Limit concurrent workers
CELERY_WORKER_CONCURRENCY=1
```

### Storage Management

Clean up old recordings:
```bash
# Remove processed files older than 30 days
docker exec autodoc-minio mc find myminio/autodoc-uploads --older-than 30d --exec "mc rm {}"
```

## 📊 System Monitoring

### Health Checks

```bash
# System status
curl http://localhost:8000/health

# Individual service checks
docker-compose ps
docker-compose logs autodoc-ai
docker-compose logs celery-worker
```

### Performance Metrics

Monitor processing times:
- **ASR**: 2-5 minutes per hour of audio
- **Step Detection**: 30-60 seconds
- **Screenshot Extraction**: 1-2 minutes
- **LLM Processing**: 1-3 minutes per step
- **TTS Generation**: 30-60 seconds per minute of speech

## 🔒 Privacy & Security

### Local Processing Benefits

- **No cloud uploads**: All AI processing happens locally
- **Data ownership**: You control all recordings and generated content
- **Compliance**: Meet GDPR/privacy requirements easily
- **Offline capability**: Works without internet connection

### Security Features

- JWT-based authentication
- Encrypted storage (MinIO with encryption)
- Secure API endpoints with rate limiting
- Private network isolation in Docker

## 🆘 Troubleshooting

### Common Issues

**Extension not recording:**
- Check microphone permissions in Chrome
- Ensure screen capture permissions are granted
- Restart Chrome and reload extension

**Processing stuck at 0%:**
```bash
# Check worker status
docker-compose logs celery-worker

# Restart processing
docker-compose restart celery-worker
```

**Can't access frontend:**
```bash
# Check if services are running
docker-compose ps

# View frontend logs
docker-compose logs autodoc-frontend
```

**Model download failing:**
```bash
# Check disk space
df -h

# Manually download models
mkdir -p ~/.cache/whisper
# Download from official sources
```

### Debug Commands

```bash
# View all logs
docker-compose logs -f

# Check system resources
docker stats

# Database access
docker exec -it autodoc-postgres psql -U autodoc -d autodoc_db

# Storage inspection
docker exec -it autodoc-minio mc ls myminio/
```

## 🎯 Best Practices

### Recording Tips

1. **Speak clearly** and at a moderate pace
2. **Pause between steps** for better segmentation
3. **Click precisely** on target elements
4. **Avoid background noise** for cleaner transcription
5. **Record in good lighting** for clearer screenshots

### Content Creation

1. **Review auto-generated steps** for accuracy
2. **Adjust marker positions** if AI misidentified click locations
3. **Refine instructions** to be more specific
4. **Test exported guides** before sharing
5. **Iterate and improve** based on user feedback

### System Maintenance

1. **Regular backups** of database and storage
2. **Monitor disk usage** for growing media files
3. **Update models** periodically for better accuracy
4. **Review logs** for error patterns
5. **Scale resources** based on usage patterns

## 📞 Support

### Community Resources

- **Documentation**: [Wiki](https://github.com/your-org/autodoc/wiki)
- **Issue Tracker**: [GitHub Issues](https://github.com/your-org/autodoc/issues)
- **Discussions**: [Community Forum](https://github.com/your-org/autodoc/discussions)

### Professional Support

For enterprise deployments:
- Email: enterprise@autodoc.ai
- SLA: 24-hour response time
- Custom development available

---

**Ready to create amazing documentation? Start recording today! 🎥📝**