// clients/vscode/extension-host/src/message_types.ts
// Mirror of ../../webview/src/message_bridge types, kept in sync manually.
// The webview package uses DOM APIs so cannot be imported directly by the
// Node.js extension host (different rootDir and lib targets).

// Messages from extension host -> webview
export type HostToWebview =
  | { type: "connect"; token: string; url: string; room: string }
  | { type: "disconnect" }
  | { type: "send_data"; payload: object };

// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "status"; state: "idle" | "explaining" | "listening" | "interrupted" };
