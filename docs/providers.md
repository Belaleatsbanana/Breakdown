# Providers

Breakdown uses three provider types: LLM (language model), TTS (text to speech),
and STT (speech to text). All are configured via environment variables in `.env`.

## LLM Providers

| Provider | Env var | Model example |
|---|---|---|
| OpenAI (default) | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-opus-4-8` |
| Groq | `GROQ_API_KEY` | `llama3-70b-8192` |
| Ollama (local) | none | `ollama/llama3` |

Set the model with `LLM_MODEL=<model>`. Breakdown uses LiteLLM for provider
routing, so any model string LiteLLM supports will work.

## TTS Providers

| Provider | Env var | Config key |
|---|---|---|
| OpenAI (default) | `OPENAI_API_KEY` | `TTS_PROVIDER=openai` |
| ElevenLabs | `ELEVENLABS_API_KEY` | `TTS_PROVIDER=elevenlabs` |

## STT Providers

| Provider | Env var | Config key |
|---|---|---|
| OpenAI Whisper (default) | `OPENAI_API_KEY` | `STT_PROVIDER=openai` |
| Deepgram | `DEEPGRAM_API_KEY` | `STT_PROVIDER=deepgram` |

## Embedding Providers

Embeddings are used for codebase indexing.

| Provider | Env var | Config key | Notes |
|---|---|---|---|
| OpenAI (default) | `OPENAI_API_KEY` | `EMBEDDING_PROVIDER=openai` | No extra key if already set |
| Local | none | `EMBEDDING_PROVIDER=local` | Downloads ~117MB model on first run |

## LiveKit

| Setup | Config |
|---|---|
| Local Docker (default if no key) | No config needed; Docker must be installed |
| LiveKit Cloud | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` |

## Adding a Provider

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the step-by-step guide.
