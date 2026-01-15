# Simple Dockerfile for static HTML/CSS/JS frontend
FROM python:3.11-alpine

WORKDIR /app

# Copy all files
COPY . .

# Install Python dependencies if needed
# RUN pip install flask

# Expose port
EXPOSE 3000

# Start server
CMD ["python", "server.py"]