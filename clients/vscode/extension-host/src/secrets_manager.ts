// clients/vscode/extension-host/src/secrets_manager.ts
// No top-level `vscode` import — this file must load under the plain
// mocha/ts-node test runner, which has no `vscode` module available.
// The real vscode.SecretStorage is structurally compatible with
// SecretStore below (Thenable and PromiseLike are the same shape).

export interface ApiKeyEntry {
  envVar: string;
  label: string;
  description: string;
}

export const API_KEY_ENTRIES: ApiKeyEntry[] = [
  { envVar: "OPENAI_API_KEY", label: "OpenAI", description: "Recommended: covers LLM, TTS, and embeddings" },
  { envVar: "ANTHROPIC_API_KEY", label: "Anthropic", description: "LLM alternate" },
  { envVar: "MISTRAL_API_KEY", label: "Mistral", description: "LLM alternate" },
  { envVar: "GROQ_API_KEY", label: "Groq", description: "LLM alternate" },
  { envVar: "OPENROUTER_API_KEY", label: "OpenRouter", description: "LLM alternate" },
  { envVar: "TOGETHER_API_KEY", label: "Together", description: "LLM alternate" },
  { envVar: "PERPLEXITY_API_KEY", label: "Perplexity", description: "LLM alternate" },
  { envVar: "DEEPGRAM_API_KEY", label: "Deepgram", description: "TTS alternate" },
  { envVar: "ELEVENLABS_API_KEY", label: "ElevenLabs", description: "TTS alternate" },
  { envVar: "JINA_API_KEY", label: "Jina", description: "Embedding alternate" },
  { envVar: "GEMINI_API_KEY", label: "Gemini", description: "Embedding alternate" },
  { envVar: "LIVEKIT_URL", label: "LiveKit Cloud URL", description: "Optional: skip self-hosted Docker, use a LiveKit Cloud project instead" },
  { envVar: "LIVEKIT_API_KEY", label: "LiveKit Cloud API Key", description: "Required alongside LiveKit Cloud URL" },
  { envVar: "LIVEKIT_API_SECRET", label: "LiveKit Cloud API Secret", description: "Required alongside LiveKit Cloud URL" },
];

const LLM_ENV_VARS = new Set([
  "OPENAI_API_KEY",
  "ANTHROPIC_API_KEY",
  "MISTRAL_API_KEY",
  "GROQ_API_KEY",
  "OPENROUTER_API_KEY",
  "TOGETHER_API_KEY",
  "PERPLEXITY_API_KEY",
]);

function storageKey(envVar: string): string {
  return `breakdown.${envVar}`;
}

export interface SecretStore {
  get(key: string): PromiseLike<string | undefined>;
  store(key: string, value: string): PromiseLike<void>;
}

export class SecretsManager {
  constructor(private readonly _secrets: SecretStore) {}

  async getStoredEnv(): Promise<Record<string, string>> {
    const env: Record<string, string> = {};
    for (const entry of API_KEY_ENTRIES) {
      const value = await this._secrets.get(storageKey(entry.envVar));
      if (value) {
        env[entry.envVar] = value;
      }
    }
    return env;
  }

  async hasAnyLlmKey(): Promise<boolean> {
    for (const envVar of LLM_ENV_VARS) {
      const value = await this._secrets.get(storageKey(envVar));
      if (value) {
        return true;
      }
    }
    return false;
  }

  async store(envVar: string, value: string): Promise<void> {
    await this._secrets.store(storageKey(envVar), value);
  }
}
