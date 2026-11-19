FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_URL=https://web-production-6e9e94b6.up.railway.app
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --prefer-binary --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-build /frontend/dist /app/frontend/dist
CMD ["python", "run.py"]
