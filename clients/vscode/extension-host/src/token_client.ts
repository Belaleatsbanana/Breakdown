// clients/vscode/extension-host/src/token_client.ts
import * as fs from "fs";
import * as path from "path";
import * as http from "http";

interface RuntimeInfo {
  port: number;
  livekit_url: string;
}

interface TokenResponse {
  token: string;
  url: string;
}

export function readRuntimeInfo(breakdownDir: string): RuntimeInfo | null {
  const runtimePath = path.join(breakdownDir, "runtime.json");
  try {
    const raw = fs.readFileSync(runtimePath, "utf-8");
    return JSON.parse(raw) as RuntimeInfo;
  } catch {
    return null;
  }
}

export async function getToken(port: number, room: string): Promise<TokenResponse> {
  return new Promise((resolve, reject) => {
    const req = http.get(
      `http://127.0.0.1:${port}/token?room=${encodeURIComponent(room)}`,
      (res) => {
        let body = "";
        res.on("data", (chunk: Buffer) => { body += chunk.toString(); });
        res.on("end", () => {
          if (res.statusCode !== 200) {
            reject(new Error(`Token server returned HTTP ${res.statusCode}: ${body}`));
            return;
          }
          try {
            resolve(JSON.parse(body) as TokenResponse);
          } catch {
            reject(new Error(`Invalid token response: ${body}`));
          }
        });
      }
    );
    req.on("error", reject);
    req.setTimeout(3000, () => {
      req.destroy();
      reject(new Error("Token server request timed out"));
    });
  });
}

export async function getTokenWithRetry(
  breakdownDir: string,
  room: string,
  maxAttempts = 10,
  delayMs = 500,
): Promise<TokenResponse> {
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const info = readRuntimeInfo(breakdownDir);
    if (info) {
      try {
        return await getToken(info.port, room);
      } catch {
        // server not ready yet
      }
    }
    if (attempt < maxAttempts) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  throw new Error(
    "Could not reach Breakdown token server. Is `breakdown start` running?"
  );
}
