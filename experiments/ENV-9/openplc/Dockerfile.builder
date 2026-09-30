FROM debian:12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgtk-3-0 libnss3 libasound2 libgbm1 libxss1 libxtst6 \
      libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
      libpango-1.0-0 libcairo2 libatspi2.0-0 ca-certificates \
 && rm -rf /var/lib/apt/lists/*
COPY OpenPLC-Editor-4.3.2.AppImage /opt/editor.AppImage
RUN chmod +x /opt/editor.AppImage && cd /opt && ./editor.AppImage --appimage-extract >/dev/null && rm editor.AppImage && ls /opt/squashfs-root | head
