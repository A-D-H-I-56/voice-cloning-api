---
title: Voice Cloning API
emoji: 🎤
colorFrom: purple
colorTo: blue
sdk: docker
---

# Voice Cloning API

A REST API for voice cloning and speech synthesis powered by [Coqui XTTS-v2](https://huggingface.co/coqui/XTTS-v2). Upload a short audio sample to create a voice clone, then synthesize speech in that voice with any text across multiple languages.

Built with **FastAPI**, **MongoDB**, and **PyTorch**.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start (Docker)](#quick-start-docker)
- [Local Development](#local-development)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [GPU Support](#gpu-support)
- [Project Structure](#project-structure)
- [Production Notes](#production-notes)

---

## Features

- **Zero-Shot Voice Cloning** — Extract speaker embeddings from a short WAV/MP3 audio sample (6-10 seconds recommended)
- **Speech Synthesis** — Generate natural-sounding speech using a cloned voice
- **Multilingual** — Supports 16+ languages
- **Clone Management** — Full CRUD: create, list, and delete voice clones
- **Async API** — Non-blocking request handling with thread-pool-based ML inference
- **Dockerized** — Multi-stage Docker build with Docker Compose orchestration
- **Persistent Storage** — Speaker embeddings and generated audio persisted via Docker volumes

---

## Architecture

```
┌──────────┐        ┌──────────────────┐        ┌──────────┐
│  Client  │──HTTP──│  FastAPI (8000)   │──async──│ MongoDB  │
└──────────┘        │                  │        │  (7.0)   │
                    │  ┌────────────┐  │        └──────────┘
                    │  │ XTTS-v2    │  │
                    │  │ (PyTorch)  │  │
                    │  └────────────┘  │
                    └──────────────────┘
                      │            │
              checkpoints/    outputs/
              (.pt files)    (.wav files)
```

- **FastAPI** serves the REST endpoints and manages async I/O
- **XTTS-v2** runs in a single-threaded pool to serialize GPU/CPU inference safely
- **MongoDB** stores clone metadata (filenames, embedding paths, timestamps)
- **Checkpoints** directory holds speaker embedding `.pt` files
- **Outputs** directory holds generated `.wav` audio files

---

## Prerequisites

- **Docker** and **Docker Compose** (recommended), or
- **Python 3.10**, **MongoDB 7.0**, and **ffmpeg** / **espeak-ng** for local development
- At least **8 GB RAM** (the XTTS-v2 model is ~2.2 GB)

---

## Quick Start (Docker)

```bash
# 1. Clone the repository
git clone <repository-url>
cd voice-cloning-api

# 2. Start the services (API + MongoDB)
docker compose up --build -d

# 3. Wait for the XTTS-v2 model to download on first run (~2.2 GB, may take 10-20 minutes)
docker compose logs -f api

# 4. Test the health endpoint
curl http://localhost:8000/health
```

The API is available at `http://localhost:8000`. Interactive Swagger docs are at `http://localhost:8000/docs`.

> **Note:** The first startup downloads the XTTS-v2 model (~2.2 GB). The model is cached in a Docker volume (`tts_model_cache`) so subsequent starts are fast.

---

## Local Development

```bash
# 1. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 2. Install PyTorch (CPU)
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start MongoDB (e.g., via Docker)
docker run -d --name mongo -p 27017:27017 mongo:7.0

# 5. Run the API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Configuration

All settings are loaded from environment variables (or a `.env` file in the project root).

| Variable           | Default                                         | Description                                   |
| ------------------ | ----------------------------------------------- | --------------------------------------------- |
| `MONGO_URI`        | `mongodb://localhost:27017`                     | MongoDB connection string                     |
| `DB_NAME`          | `voice_cloning`                                 | MongoDB database name                         |
| `CHECKPOINTS_DIR`  | `checkpoints`                                   | Directory for speaker embedding `.pt` files   |
| `OUTPUTS_DIR`      | `outputs`                                       | Directory for generated WAV files             |
| `TTS_MODEL`        | `tts_models/multilingual/multi-dataset/xtts_v2` | Coqui TTS model identifier                    |
| `SAMPLE_RATE`      | `24000`                                         | Output audio sample rate (Hz)                 |
| `COQUI_TOS_AGREED` | `1`                                             | Auto-accept Coqui CPML non-commercial license |

> When running via Docker Compose, `MONGO_URI` is automatically overridden to `mongodb://mongodb:27017` so the API reaches the MongoDB container by service name.

---

## API Reference

Base URL: `http://localhost:8000`

| Method   | Endpoint            | Description                                     |
| -------- | ------------------- | ----------------------------------------------- |
| `GET`    | `/health`           | Service health check                            |
| `POST`   | `/clone`            | Upload reference audio and create a voice clone |
| `GET`    | `/clones`           | List all saved voice clones                     |
| `DELETE` | `/clone/{clone_id}` | Delete a clone and all associated files         |
| `POST`   | `/speak`            | Synthesize speech using a cloned voice          |

---

### Health Check

```
GET /health
```

**Response:**

```json
{
  "status": "ok",
  "tts_device": "cpu",
  "model": "tts_models/multilingual/multi-dataset/xtts_v2"
}
```

---

### Create a Voice Clone

```
POST /clone
Content-Type: multipart/form-data
```

Upload a reference audio file (`.wav` or `.mp3`) to extract speaker embeddings and create a voice clone.

**Request:**

```bash
curl -X POST http://localhost:8000/clone \
  -F "file=@reference_audio.wav"
```

**Response** `201 Created`:

```json
{
  "clone_id": "6651a3f4e4b0f1c2d3e4f5a6",
  "original_filename": "reference_audio.wav",
  "embedding_path": "checkpoints/6651a3f4e4b0f1c2d3e4f5a6.pt",
  "created_at": "2025-01-15T10:30:00Z"
}
```

| Status | Description                                             |
| ------ | ------------------------------------------------------- |
| `201`  | Clone created successfully                              |
| `415`  | Unsupported file type (only `.wav` and `.mp3` accepted) |
| `500`  | Embedding extraction failed                             |

---

### List All Clones

```
GET /clones
```

**Response** `200 OK`:

```json
[
  {
    "clone_id": "6651a3f4e4b0f1c2d3e4f5a6",
    "original_filename": "reference_audio.wav",
    "created_at": "2025-01-15T10:30:00Z"
  }
]
```

---

### Delete a Clone

```
DELETE /clone/{clone_id}
```

Removes the speaker embedding file, all generated audio outputs, and the database record.

**Response** `200 OK`:

```json
{
  "deleted": true,
  "clone_id": "6651a3f4e4b0f1c2d3e4f5a6",
  "message": "Clone and all associated files removed."
}
```

| Status | Description                |
| ------ | -------------------------- |
| `200`  | Clone deleted successfully |
| `404`  | Clone not found            |

---

### Synthesize Speech

```
POST /speak
Content-Type: application/json
```

Generate speech using a cloned voice. Returns the audio as a WAV file download.

**Request:**

```bash
curl -X POST http://localhost:8000/speak \
  -H "Content-Type: application/json" \
  -d '{"clone_id": "6651a3f4e4b0f1c2d3e4f5a6", "text": "Hello, this is my cloned voice!", "language": "en"}' \
  --output speech.wav
```

**Request Body:**

| Field      | Type   | Required | Description                            |
| ---------- | ------ | -------- | -------------------------------------- |
| `clone_id` | string | Yes      | ID of the voice clone to use           |
| `text`     | string | Yes      | Text to synthesize (1-4096 characters) |
| `language` | string | No       | BCP-47 language code (default: `"en"`) |

**Response** `200 OK`: Binary WAV audio file (`audio/wav`)

Response headers include `X-Clone-ID` and `X-Output-Path`.

| Status | Description                                          |
| ------ | ---------------------------------------------------- |
| `200`  | Audio generated successfully                         |
| `400`  | Embedding file missing on disk — re-create the clone |
| `404`  | Clone not found                                      |
| `500`  | Synthesis failed                                     |

---

## GPU Support

The default Docker setup uses CPU inference. To enable NVIDIA GPU acceleration:

1. Install [nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) on the host.

2. Uncomment the GPU block in `docker-compose.yml`:

   ```yaml
   deploy:
     resources:
       reservations:
         devices:
           - driver: nvidia
             count: 1
             capabilities: [gpu]
   ```

3. Update the PyTorch install in the `Dockerfile` to use a CUDA index:

   ```dockerfile
   RUN pip install --no-cache-dir \
       torch \
       torchaudio \
       --index-url https://download.pytorch.org/whl/cu121
   ```

4. Rebuild:

   ```bash
   docker compose up --build -d
   ```

The application auto-detects CUDA and will report the device via `GET /health`.

---

## Project Structure

```
voice-cloning-api/
├── app/
│   ├── __init__.py
│   ├── config.py            # Pydantic settings (env vars)
│   ├── database.py          # Async MongoDB operations (Motor)
│   ├── main.py              # FastAPI app, lifespan, health endpoint
│   ├── models.py            # Request/response Pydantic schemas
│   ├── tts_engine.py        # XTTS-v2 singleton (embedding extraction + synthesis)
│   └── routes/
│       ├── __init__.py
│       ├── clone_routes.py  # POST /clone, GET /clones, DELETE /clone/{id}
│       └── speak_routes.py  # POST /speak
├── checkpoints/             # Speaker embedding .pt files (git-ignored)
├── outputs/                 # Generated WAV files (git-ignored)
├── .env                     # Environment variables
├── .dockerignore
├── .gitignore
├── docker-compose.yml       # API + MongoDB service orchestration
├── Dockerfile               # Multi-stage build (builder + runtime)
├── requirements.txt         # Python dependencies
└── README.md
```

---

## Production Notes

- **CPU vs GPU**: Inference on CPU is significantly slower than GPU. A single synthesis request may take several seconds on CPU.
- **Single Worker**: The app runs with one Uvicorn worker to avoid loading multiple copies of the model into memory. Scale horizontally at the container level instead.
- **Concurrency**: All ML inference is serialized through a single-threaded pool — only one inference call runs at a time to safely manage GPU/CPU resources while keeping the async event loop responsive.
- **Persistence**: Speaker embeddings (`checkpoints/`) and generated audio (`outputs/`) are bind-mounted from the host via Docker Compose, so data survives container restarts and rebuilds.
- **Model Cache**: The XTTS-v2 model is stored in a named Docker volume (`tts_model_cache`) to avoid re-downloading on rebuilds.
- **CORS**: Update `allow_origins` in `main.py` if deploying behind a frontend application.
