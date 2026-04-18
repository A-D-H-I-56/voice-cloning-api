# ---------------------------------------------------------------------------
# Stage 1 — dependency installer
# Python packages are built into an isolated venv that is copied to stage 2,
# keeping compiler tooling out of the final image.
# ---------------------------------------------------------------------------
FROM python:3.10-slim AS builder

WORKDIR /build

# Build tools required by native Python extensions (numpy, trainer, etc.)
# Rust toolchain is needed for sudachipy (a transitive dependency of coqui-tts).
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        git \
        rustc \
        cargo \
    && rm -rf /var/lib/apt/lists/*

# Create the venv that will be shipped to the runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# ── PyTorch (CPU) ──────────────────────────────────────────────────────────
# Installed first and from the PyTorch CPU index to avoid pulling the large
# CUDA wheel. For GPU, swap the index URL for the matching CUDA build, e.g.:
#   https://download.pytorch.org/whl/cu121
RUN pip install --no-cache-dir \
        torch \
        torchaudio \
        --index-url https://download.pytorch.org/whl/cpu

# ── All other dependencies ─────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


# ---------------------------------------------------------------------------
# Stage 2 — lean runtime image
# ---------------------------------------------------------------------------
FROM python:3.10-slim

# Runtime system libraries
# libgomp1    — OpenMP, required by PyTorch CPU inference
# libsndfile1 — required by soundfile / torchaudio for WAV I/O
# espeak-ng   — phonemiser used by Coqui TTS for several languages
# ffmpeg      — audio decoding/encoding used by torchaudio & coqui-tts
# curl        — used by docker-compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libsndfile1 \
        espeak-ng \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy the pre-built venv from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Activate the venv for all subsequent RUN / CMD instructions
ENV PATH="/opt/venv/bin:$PATH" \
    VIRTUAL_ENV="/opt/venv"

WORKDIR /app

# Copy application source only (no venv, no outputs, no checkpoints)
COPY app/ ./app/

# Pre-create persistent storage directories and setup permissions for Hugging Face Spaces (User 1000)
RUN useradd -m -u 1000 user
RUN mkdir -p checkpoints outputs && chown -R user:user /app checkpoints outputs

USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

EXPOSE 7860

# Single worker — multiple workers would each load a copy of the model,
# multiplying RAM/VRAM usage. Scale horizontally at the container level instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]
