FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive NO_AT_BRIDGE=1 DISPLAY=:1 LANG=C.UTF-8
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv python3-pip python3-gi python3-gi-cairo \
    gir1.2-gtk-3.0 gir1.2-webkit2-4.1 xvfb x11vnc openbox novnc websockify dbus dbus-x11 git ca-certificates \
    fonts-dejavu-core fonts-noto-color-emoji libgl1-mesa-dri \
 && rm -rf /var/lib/apt/lists/* \
 && useradd -m -s /bin/bash uds \
 && mkdir /app && chown uds:uds /app
WORKDIR /app
COPY --chown=uds:uds . /app
USER uds
RUN python3 -m venv --system-site-packages .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt
EXPOSE 6080
ENTRYPOINT ["sh", "/app/docker/start.sh"]
