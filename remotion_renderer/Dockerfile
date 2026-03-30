FROM node:20-slim

# Install only the essential dependencies for Chrome Headless Shell + FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk-bridge2.0-0 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libxshmfence1 \
    fonts-liberation \
    fonts-noto-color-emoji \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    ffmpeg \
    dbus \
    && rm -rf /var/lib/apt/lists/*

# Required for running headless Chrome in Docker
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

WORKDIR /app

# Copy package files and install dependencies
COPY package*.json ./
RUN npm install

# Copy the rest of the app
COPY . .

# Pre-download Chrome Headless Shell at build time (not at runtime)
# This prevents the 108MB download during rendering and saves memory
RUN npx remotion browser ensure

# Expose the port (Railway will inject PORT env var)
EXPOSE 8090

# Start the server
CMD ["npm", "start"]
