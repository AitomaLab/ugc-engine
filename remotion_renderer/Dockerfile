FROM node:20-slim

# Install Chromium and all required dependencies for Remotion rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
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

# Tell Puppeteer/Remotion to skip downloading its own Chromium
ENV PUPPETEER_SKIP_DOWNLOAD=true
# Point Remotion to the system-installed Chromium
ENV REMOTION_CHROME_EXECUTABLE=/usr/bin/chromium
# Required for running Chromium in Docker (no display, no sandbox)
ENV CHROMIUM_FLAGS="--no-sandbox"
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN npm ci --production=false

# Copy the rest of the app
COPY . .

# Expose the port (Railway will inject PORT env var)
EXPOSE 8090

# Start the server
CMD ["npm", "start"]
