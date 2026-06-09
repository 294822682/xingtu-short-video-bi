FROM node:24-bookworm-slim AS frontend

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci
RUN npm install -g univer-cli@0.1.25

COPY index.html vite.config.js ./
COPY frontend ./frontend
RUN npm run build

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV XINGTU_DATA_DIR=/data/current

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=frontend /usr/local/bin/node /usr/local/bin/node
COPY --from=frontend /usr/local/lib/node_modules/univer-cli /usr/local/lib/node_modules/univer-cli
RUN ln -s /usr/local/lib/node_modules/univer-cli/bin/univer.js /usr/local/bin/univer \
    && univer --help >/dev/null

COPY app ./app
COPY --from=frontend /app/dist ./dist

RUN mkdir -p /data/current

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
