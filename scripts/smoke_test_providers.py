#!/usr/bin/env python3
"""Smoke test all configured providers. Run before opening a PR that touches providers."""
from __future__ import annotations

import sys
from breakdown.config import get_settings
from loguru import logger


def test_openai_llm() -> bool:
    try:
        import openai
        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        client.models.list()
        logger.info("OpenAI LLM: ok")
        return True
    except Exception as e:
        logger.error("OpenAI LLM: {}", e)
        return False


def test_openai_tts() -> bool:
    try:
        import openai
        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        client.audio.speech.create(model="tts-1", voice="alloy", input="test")
        logger.info("OpenAI TTS: ok")
        return True
    except Exception as e:
        logger.error("OpenAI TTS: {}", e)
        return False


def test_openai_stt() -> bool:
    try:
        import openai, io
        client = openai.OpenAI(api_key=get_settings().openai_api_key)
        # minimal silent WAV for smoke test
        silent_wav = bytes([
            0x52, 0x49, 0x46, 0x46, 0x24, 0x00, 0x00, 0x00, 0x57, 0x41, 0x56,
            0x45, 0x66, 0x6D, 0x74, 0x20, 0x10, 0x00, 0x00, 0x00, 0x01, 0x00,
            0x01, 0x00, 0x44, 0xAC, 0x00, 0x00, 0x88, 0x58, 0x01, 0x00, 0x02,
            0x00, 0x10, 0x00, 0x64, 0x61, 0x74, 0x61, 0x00, 0x00, 0x00, 0x00,
        ])
        client.audio.transcriptions.create(
            model="whisper-1", file=("test.wav", io.BytesIO(silent_wav), "audio/wav")
        )
        logger.info("OpenAI STT: ok")
        return True
    except Exception as e:
        logger.error("OpenAI STT: {}", e)
        return False


if __name__ == "__main__":
    results = [test_openai_llm(), test_openai_tts(), test_openai_stt()]
    if not all(results):
        logger.error("Some providers failed. Check your API keys in .env.")
        sys.exit(1)
    logger.info("All providers healthy.")
