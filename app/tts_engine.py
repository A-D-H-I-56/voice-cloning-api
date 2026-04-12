"""
TTS Engine — Singleton wrapper around the XTTS-v2 model.

Design decisions:
  - Lazy loaded on first API request (not at startup) to support HF Spaces.
  - Allows fast startup and immediate health checks.
  - A single ThreadPoolExecutor (max_workers=1) serialises all GPU/CPU calls
    so only one inference runs at a time and the async event loop is never blocked.
  - torch.inference_mode() reduces memory overhead during inference.
"""

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Tuple

import torch
from app.config import settings

logger = logging.getLogger(__name__)

# One worker is intentional: a single GPU cannot parallelise two XTTS passes.
_executor = ThreadPoolExecutor(max_workers=1)


class TTSEngine:
    def __init__(self) -> None:
        self._model = None
        self._device: Optional[str] = None
        self._loading = False

    # ------------------------------------------------------------------
    # Lazy Loading (on first use, not at startup)
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Ensure model is loaded. Thread-safe for concurrent access."""
        if self._model is not None:
            return  # Already loaded

        if self._loading:
            # Wait for another thread to finish loading
            while self._loading and self._model is None:
                time.sleep(0.1)
            return

        self._loading = True
        try:
            self._load_model()
        finally:
            self._loading = False

    def _load_model(self) -> None:
        """Internal method to load the model."""
        from TTS.api import TTS  # deferred so import errors surface clearly

        # Auto-accept Coqui's non-commercial CPML licence.
        os.environ.setdefault("COQUI_TOS_AGREED", "1")

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading TTS model on device: %s", self._device)

        # TTS() downloads the model on first run and caches it locally.
        self._model = TTS(settings.tts_model).to(self._device)
        logger.info("TTS model loaded successfully.")

    # ------------------------------------------------------------------
    # Public helpers (synchronous, to be called inside the thread pool)
    # ------------------------------------------------------------------

    def _extract_embeddings(
        self, audio_path: str
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Return (gpt_cond_latent, speaker_embedding) for *audio_path*."""
        self._ensure_loaded()  # Load if not already loaded
        with torch.inference_mode():
            gpt_cond_latent, speaker_embedding = (
                self._model.synthesizer.tts_model.get_conditioning_latents(
                    audio_path=[audio_path]
                )
            )
        return gpt_cond_latent, speaker_embedding

    def _synthesize(
        self,
        text: str,
        language: str,
        gpt_cond_latent: torch.Tensor,
        speaker_embedding: torch.Tensor,
    ) -> torch.Tensor:
        """Run XTTS inference and return a 1-D float32 waveform tensor."""
        self._ensure_loaded()  # Load if not already loaded
        with torch.inference_mode():
            out = self._model.synthesizer.tts_model.inference(
                text=text,
                language=language,
                gpt_cond_latent=gpt_cond_latent,
                speaker_embedding=speaker_embedding,
                temperature=0.7,
                length_penalty=1.0,
                repetition_penalty=10.0,
                top_k=50,
                top_p=0.85,
                enable_text_splitting=True,
            )
        return torch.FloatTensor(out["wav"])

    # ------------------------------------------------------------------
    # Async public API (offload blocking work to the thread pool)
    # ------------------------------------------------------------------

    async def extract_and_save_embeddings(
        self, audio_path: str, embedding_path: str
    ) -> None:
        """Extract speaker embeddings and persist them as a .pt file."""
        loop = asyncio.get_running_loop()

        gpt_cond_latent, speaker_embedding = await loop.run_in_executor(
            _executor, self._extract_embeddings, audio_path
        )

        def _save():
            torch.save(
                {
                    "gpt_cond_latent": gpt_cond_latent,
                    "speaker_embedding": speaker_embedding,
                },
                embedding_path,
            )

        await loop.run_in_executor(_executor, _save)

    async def synthesize_and_save(
        self,
        text: str,
        language: str,
        embedding_path: str,
        output_path: str,
    ) -> None:
        """Load embeddings, run synthesis, and write the WAV to *output_path*."""
        loop = asyncio.get_running_loop()

        # Load embeddings
        def _load_embeddings():
            data = torch.load(embedding_path, map_location=self._device)
            return data["gpt_cond_latent"], data["speaker_embedding"]

        gpt_cond_latent, speaker_embedding = await loop.run_in_executor(
            _executor, _load_embeddings
        )

        # Synthesise
        wav = await loop.run_in_executor(
            _executor,
            self._synthesize,
            text,
            language,
            gpt_cond_latent,
            speaker_embedding,
        )

        # Persist as WAV
        def _save_wav():
            import scipy.io.wavfile
            import numpy as np
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            scipy.io.wavfile.write(
                output_path, settings.sample_rate, wav.numpy().astype(np.float32)
            )

        await loop.run_in_executor(_executor, _save_wav)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @property
    def device(self) -> Optional[str]:
        if self._device is None:
            # If not yet loaded, detect device
            return "cuda" if torch.cuda.is_available() else "cpu"
        return self._device

    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded."""
        return self._model is not None


# Module-level singleton — import this everywhere else.
tts_engine = TTSEngine()
