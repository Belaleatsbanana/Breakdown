// clients/vscode/extension-host/src/message_types.ts
// Mirror of ../../webview/src/message_bridge types, kept in sync manually.
// The webview package uses DOM APIs so cannot be imported directly by the
// Node.js extension host (different rootDir and lib targets).

// Messages from extension host -> webview
export type HostToWebview =
  | { type: "connect"; token: string; url: string; room: string }
  | { type: "disconnect" }
  | {
      type: "rpc";
      method: "explain" | "ask" | "next" | "prev" | "stop";
      payload: object;
    };

// Messages from webview -> extension host
export type WebviewToHost =
  | { type: "ready" }
  | { type: "connected"; participantId: string }
  | { type: "disconnected"; reason: string }
  | { type: "error"; message: string }
  | { type: "rpc_start"; method: string }
  | { type: "rpc_end"; method: string }
  | { type: "position"; file: string; line: number };
