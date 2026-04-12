# 🎤 Voice Cloning API

Create realistic voice clones from short audio samples and synthesize natural-sounding speech using those voices.

**Powered by:** Coqui XTTS-v2 | **Stack:** FastAPI + PyTorch + MongoDB Atlas | **Status:** ✅ Production Ready

---

## ✨ Features

- **🎯 Zero-Shot Voice Cloning** — Clone any voice from 6-10 second audio sample
- **🗣️ Multilingual** — Support for 16+ languages
- **⚡ Fast** — GPU-accelerated inference (~1-2 sec per synthesis)
- **🔐 Secure** — API key authentication + rate limiting
- **💾 Persistent** — Embeddings stored in MongoDB Atlas
- **📦 Easy** — RESTful API, no complex setup

---

## 🚀 Quick Start

### 1️⃣ Get Your API Key

Your API key is available in the **"Settings"** tab on this Space.

**Save it safely** — it authenticates all your requests.

```bash
API_KEY="your-api-key-here"
```

### 2️⃣ Create a Voice Clone

Upload a 6-10 second audio sample (WAV or MP3):

```bash
curl -X POST https://huggingface.co/spaces/YOUR_USERNAME/voice-cloning-api/clone \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@my_voice.wav"
```

**Response:**

```json
{
  "clone_id": "507f1f77bcf86cd799439011",
  "original_filename": "my_voice.wav",
  "embedding_path": "checkpoints/507f1f77bcf86cd799439011.pt",
  "created_at": "2026-04-12T12:30:00Z"
}
```

**Save the `clone_id`** — you'll use it for synthesis!

### 3️⃣ Synthesize Speech

Generate audio using your cloned voice:

```bash
curl -X POST https://huggingface.co/spaces/YOUR_USERNAME/voice-cloning-api/speak \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "clone_id": "507f1f77bcf86cd799439011",
    "text": "Hello! This is my cloned voice!",
    "language": "en"
  }' \
  --output speech.wav
```

**Done!** 🎉 You now have `speech.wav` with your voice!

### 4️⃣ List Your Clones

```bash
curl -X GET https://huggingface.co/spaces/YOUR_USERNAME/voice-cloning-api/clones \
  -H "Authorization: Bearer $API_KEY"
```

### 5️⃣ Delete a Clone

```bash
curl -X DELETE https://huggingface.co/spaces/YOUR_USERNAME/voice-cloning-api/clone/507f1f77bcf86cd799439011 \
  -H "Authorization: Bearer $API_KEY"
```

---

## 📊 Supported Languages

```
en (English)        | es (Spanish)       | fr (French)
de (German)         | it (Italian)       | pt (Portuguese)
nl (Dutch)          | pl (Polish)        | tr (Turkish)
ru (Russian)        | sv (Swedish)       | ja (Japanese)
zh (Chinese)        | ar (Arabic)        | cs (Czech)
```

---

## ⚙️ API Reference

| Endpoint      | Method | Auth | Purpose                       |
| ------------- | ------ | ---- | ----------------------------- |
| `/health`     | GET    | ❌   | Check if API is running       |
| `/clone`      | POST   | ✅   | Create voice clone from audio |
| `/clones`     | GET    | ✅   | List all your clones          |
| `/clone/{id}` | DELETE | ✅   | Delete a clone                |
| `/speak`      | POST   | ✅   | Synthesize audio              |

### Request/Response Details

#### POST /clone

```bash
Request (multipart/form-data):
  file: <audio file (WAV/MP3, max 50MB)>

Response (201 Created):
{
  "clone_id": "...",
  "original_filename": "...",
  "embedding_path": "...",
  "created_at": "2026-04-12T..."
}
```

#### POST /speak

```bash
Request (application/json):
{
  "clone_id": "507f1f77bcf86cd799439011",
  "text": "Hello world",
  "language": "en"  # optional, default "en"
}

Response (200 OK):
  Binary WAV audio file
  Headers: X-Clone-ID, X-Output-Path
```

---

## 🛡️ Security & Limits

| Feature         | Limit                  | Notes                                       |
| --------------- | ---------------------- | ------------------------------------------- |
| **File Upload** | 50 MB per file         | WAV/MP3 only                                |
| **Text Length** | 4096 characters max    | Per synthesis request                       |
| **Rate Limit**  | 10 requests/min per IP | Returns HTTP 429 when exceeded              |
| **Auth**        | Bearer token (API key) | Required for all endpoints except `/health` |

---

## ⏱️ Performance

| Operation            | Typical Time | Notes                         |
| -------------------- | ------------ | ----------------------------- |
| **Clone Creation**   | 30-60 sec    | Depends on audio processing   |
| **Synthesis** (1st)  | 5-30 sec     | Model loads to GPU first time |
| **Synthesis** (next) | 1-2 sec      | Model cached in memory        |

> **First request slower?** The XTTS-v2 model (~2.2GB) needs to load into GPU memory on first use. Subsequent requests are much faster!

---

## 🔧 Troubleshooting

### ❌ "Invalid API Key"

- Get your key from **"Settings"** on this Space
- Include it in every request: `Authorization: Bearer YOUR_KEY`

### ❌ "Clone Not Found"

- Verify the `clone_id` is correct (copy-paste from list)
- Make sure it's from YOUR account (not someone else's)

### ❌ "File Too Large"

- Max 50 MB per upload
- Compress your audio, or split into chunks

### ❌ "Rate Limit Exceeded" (429)

- Wait 60 seconds before next request
- Header `Retry-After` shows seconds to wait

### ❌ Connection Timeout

- First request on cold start might take 60+ seconds
- Be patient! Model is downloading (~2.2GB)

---

## 💡 Tips & Tricks

✅ **Best voice samples:**

- Clear, clean audio (low background noise)
- 6-10 seconds duration
- Neutral tone works better than emotional

✅ **Best synthesis:**

- Keep text under 1000 characters per request
- Shorter sentences sound more natural
- Break long text into multiple requests

❌ **Avoid:**

- Noisy/echo-y recordings
- Very short samples (< 3 sec)
- Extremely long synthesis requests

---

## 📚 Full Documentation

For complete API docs, architecture details, and deployment info:
👉 [Full README on GitHub](https://github.com/your-username/voice-cloning-api)

---

## 🤝 Support

Issues?

- Check the **Troubleshooting** section above
- Review your API key in Settings
- Verify MongoDB connection in logs

---

## 📜 License

OpenRAIL-M (Responsible AI License)

This model is governed by the [OpenRAIL](https://rai.allenai.org/model_card) principles. See the full license for responsible use guidelines.

---

**Made with ❤️ | Powered by Coqui XTTS-v2**
