FROM node:22-alpine

WORKDIR /app

# Install dependencies first for Docker layer caching
COPY frontend/package.json ./
RUN npm install

# Copy frontend source code
COPY frontend ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
