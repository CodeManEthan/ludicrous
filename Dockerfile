# Ludicrous — stdlib only, so the image is just Python + the source tree.
FROM python:3.12-slim

WORKDIR /app
COPY . .

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "python server.py --host 0.0.0.0 --port ${PORT}"]
