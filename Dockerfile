# Kit Médico Caseiro — pequena app web Flask, sem Bluetooth/LAN especial.
FROM python:3.11-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8001
# -u = sem buffer, para os logs aparecerem em tempo real no `docker logs`.
CMD ["python", "-u", "app.py"]
