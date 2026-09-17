# Stage 1: Build stage
#FROM python:3.12-slim AS builder
FROM python:3.10.21-alpine3.24 AS builder

WORKDIR /app

#RUN apt-get update && apt-get install -y --no-install-recommends \
#    gcc \
#    libc6-dev \
#    && rm -rf /var/lib/apt/lists/*
RUN apk add --no-cache \
    gcc \
    musl-dev \
    jpeg-dev \
    zlib-dev


COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Final stage
FROM python:3.10.21-alpine3.24

WORKDIR /app

RUN apk add --no-cache \
    libjpeg-turbo \
    zlib

COPY --from=builder /install /usr/local
COPY . .
#COPY app.py .
#COPY static ./static

EXPOSE 8000

CMD ["python", "app.py"]