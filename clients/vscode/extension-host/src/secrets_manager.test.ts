// clients/vscode/extension-host/src/secrets_manager.test.ts
import assert from "node:assert/strict";
import { SecretsManager, type SecretStore } from "./secrets_manager";

class FakeSecretStore implements SecretStore {
  private _store = new Map<string, string>();

  async get(key: string): Promise<string | undefined> {
    return this._store.get(key);
  }

  async store(key: string, value: string): Promise<void> {
    this._store.set(key, value);
  }
}

describe("SecretsManager", () => {
  it("hasAnyLlmKey() is false when nothing is stored", async () => {
    const manager = new SecretsManager(new FakeSecretStore());
    assert.equal(await manager.hasAnyLlmKey(), false);
  });

  it("hasAnyLlmKey() is true once an LLM key is stored", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.OPENAI_API_KEY", "sk-test");
    const manager = new SecretsManager(store);
    assert.equal(await manager.hasAnyLlmKey(), true);
  });

  it("hasAnyLlmKey() ignores non-LLM keys (TTS/embedding alternates)", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.JINA_API_KEY", "jina-test");
    const manager = new SecretsManager(store);
    assert.equal(await manager.hasAnyLlmKey(), false);
  });

  it("hasAnyLlmKey() ignores a stored LIVEKIT_URL (not an LLM key)", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.LIVEKIT_URL", "wss://my-project.livekit.cloud");
    const manager = new SecretsManager(store);
    assert.equal(await manager.hasAnyLlmKey(), false);
  });

  it("getStoredEnv() includes a stored LIVEKIT_URL alongside API keys", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.OPENAI_API_KEY", "sk-test");
    await store.store("breakdown.LIVEKIT_URL", "wss://my-project.livekit.cloud");
    const manager = new SecretsManager(store);
    assert.deepEqual(await manager.getStoredEnv(), {
      OPENAI_API_KEY: "sk-test",
      LIVEKIT_URL: "wss://my-project.livekit.cloud",
    });
  });

  it("getStoredEnv() returns only the keys that are set, by env var name", async () => {
    const store = new FakeSecretStore();
    await store.store("breakdown.OPENAI_API_KEY", "sk-test");
    await store.store("breakdown.JINA_API_KEY", "jina-test");
    const manager = new SecretsManager(store);
    assert.deepEqual(await manager.getStoredEnv(), {
      OPENAI_API_KEY: "sk-test",
      JINA_API_KEY: "jina-test",
    });
  });

  it("getStoredEnv() returns an empty object when nothing is stored", async () => {
    const manager = new SecretsManager(new FakeSecretStore());
    assert.deepEqual(await manager.getStoredEnv(), {});
  });

  it("store() prefixes the storage key with breakdown.", async () => {
    const store = new FakeSecretStore();
    const manager = new SecretsManager(store);
    await manager.store("OPENAI_API_KEY", "sk-test");
    assert.equal(await store.get("breakdown.OPENAI_API_KEY"), "sk-test");
  });
});
