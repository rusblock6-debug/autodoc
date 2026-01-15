# Frontend Dockerfile for React/Vite application
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application files
COPY . .

# Expose port
EXPOSE 3000

# Start Vite dev server (for development)
# For production, use: npm run build && npm run preview
CMD ["npm", "run", "dev"]
