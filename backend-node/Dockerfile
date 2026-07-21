# Use Node.js LTS base image
FROM node:20-slim

# Set working directory inside the container
WORKDIR /app

# Copy package files from the backend-node directory
COPY backend-node/package*.json ./

# Install production dependencies
RUN npm ci --only=production

# Copy Node.js backend source code
COPY backend-node/ ./

# Copy frontend static files to the expected sibling directory (/frontend)
# server.js resolves it via path.join(__dirname, '..', 'frontend') which matches /frontend
COPY frontend/ /frontend/

# Expose port 5000 (gateway's default port, overridden by PORT env)
EXPOSE 5000

# Start the Node.js server
CMD ["node", "server.js"]
