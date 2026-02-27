# Stage 1: Build frontend
FROM node:alpine AS builder-frontend
WORKDIR /frontend

# Copy package files
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install pnpm and dependencies
RUN npm install -g pnpm && \
    pnpm install --frozen-lockfile

# Copy frontend source and build
COPY frontend/ ./
RUN pnpm run build

# Stage 2: Python runtime with backend + built frontend
FROM python:3.14-slim
WORKDIR /app

# Install uv for faster Python dependency management
RUN pip install --no-cache-dir uv

# Copy Python dependency specs
COPY pyproject.toml uv.lock .python-version ./

# Install Python dependencies
RUN uv sync --frozen

# Copy backend code
COPY backend/ ./backend/

# Copy built frontend from stage 1
COPY --from=builder-frontend /frontend/dist ./frontend/dist

# Create data directory for volume mount
RUN mkdir -p /app/data

# Expose ports
EXPOSE 8001 5173

# Start both backend and frontend
# Backend: uvicorn on 8001
# Frontend: Python http.server on 5173
CMD ["sh", "-c", "uv run uvicorn backend.main:app --host 0.0.0.0 --port 8001 & python3 -m http.server 5173 --bind 0.0.0.0 --directory frontend/dist"]
