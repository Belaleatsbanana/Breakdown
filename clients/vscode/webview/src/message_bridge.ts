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

declare function acquireVsCodeApi(): {
  postMessage(msg: WebviewToHost): void;
  getState(): unknown;
  setState(state: unknown): void;
};

export function createBridge() {
  const vscode = acquireVsCodeApi();

  function send(msg: WebviewToHost): void {
    vscode.postMessage(msg);
  }

  function onMessage(handler: (msg: HostToWebview) => void): void {
    window.addEventListener("message", (event: MessageEvent<HostToWebview>) => {
      handler(event.data);
    });
  }

  return { send, onMessage };
}
