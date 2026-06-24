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
