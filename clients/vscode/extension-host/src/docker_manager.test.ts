// clients/vscode/extension-host/src/docker_manager.test.ts
import assert from "node:assert/strict";
import { DockerManager } from "./docker_manager";

describe("DockerManager", () => {
  it("ensureRunning() throws an actionable error when docker info fails every retry", async () => {
    let dockerInfoCalls = 0;
    const exec = async (command: string): Promise<void> => {
      if (command === "docker info") {
        dockerInfoCalls += 1;
        throw new Error("docker: command not found");
      }
    };
    const manager = new DockerManager(exec, async () => true, 30, 500, 2, 5);
    await assert.rejects(
      () => manager.ensureRunning("/fake/ext/path"),
      /Docker isn't running/,
    );
    assert.equal(dockerInfoCalls, 2);
  });

  it("ensureRunning() succeeds if docker info recovers on a later retry", async () => {
    let dockerInfoCalls = 0;
    const exec = async (command: string): Promise<void> => {
      if (command === "docker info") {
        dockerInfoCalls += 1;
        if (dockerInfoCalls < 2) {
          throw new Error("transient failure");
        }
      }
    };
    const manager = new DockerManager(exec, async () => true, 30, 500, 3, 5);
    await manager.ensureRunning("/fake/ext/path");
    assert.equal(dockerInfoCalls, 2);
  });

  it("ensureRunning() runs docker compose up with the bundled compose file path", async () => {
    const calls: string[] = [];
    const exec = async (command: string): Promise<void> => {
      calls.push(command);
    };
    const manager = new DockerManager(exec, async () => true);
    await manager.ensureRunning("/fake/ext/path");
    assert.equal(calls[0], "docker info");
    assert.match(calls[1], /docker compose -f "\/fake\/ext\/path\/resources\/docker-compose\.livekit\.yml" up -d/);
  });

  it("ensureRunning() polls until the port check succeeds", async () => {
    let checkCount = 0;
    const exec = async (): Promise<void> => {};
    const checkPort = async (): Promise<boolean> => {
      checkCount += 1;
      return checkCount >= 3;
    };
    const manager = new DockerManager(exec, checkPort, 10, 5);
    await manager.ensureRunning("/fake/ext/path");
    assert.equal(checkCount, 3);
  });

  it("ensureRunning() throws after exhausting retries if LiveKit never becomes ready", async () => {
    const exec = async (): Promise<void> => {};
    const manager = new DockerManager(exec, async () => false, 3, 5);
    await assert.rejects(
      () => manager.ensureRunning("/fake/ext/path"),
      /LiveKit did not become ready/,
    );
  });
});
