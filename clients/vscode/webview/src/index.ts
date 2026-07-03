// clients/vscode/webview/src/index.ts
import { createBridge, type HostToWebview } from "./message_bridge";
import { LiveKitRoom } from "./livekit_room";
import { ChatView } from "./chat_view";

const bridge = createBridge();
let room: LiveKitRoom | null = null;

const container = document.getElementById("turns");
if (!container) {
  throw new Error("Breakdown webview: #turns container missing from HTML shell.");
}
const chatView = new ChatView(container);

bridge.send({ type: "ready" });

bridge.onMessage(async (msg: HostToWebview) => {
  if (msg.type === "connect") {
    room = new LiveKitRoom(bridge.send);
    try {
      await room.connect(msg.url, msg.token);
    } catch (err) {
      bridge.send({ type: "error", message: String(err) });
    }
    return;
  }

  if (msg.type === "disconnect") {
    await room?.disconnect();
    room = null;
    return;
  }

  if (msg.type === "rpc") {
    if (!room) {
      bridge.send({ type: "error", message: "Breakdown: not connected." });
      return;
    }
    bridge.send({ type: "rpc_start", method: msg.method });
    try {
      const raw = await room.performRpc(msg.method, msg.payload);
      const data = JSON.parse(raw) as { text?: string; file?: string; line?: number };
      if (msg.method === "explain" && data.text !== undefined) {
        chatView.addExplainTurn(data.file ?? "", data.line ?? 0, data.text);
      } else if (msg.method === "ask" && data.text !== undefined) {
        const question =
          "text" in msg.payload ? String((msg.payload as { text: string }).text) : "";
        chatView.addAskTurn(question, data.text);
      } else if ((msg.method === "next" || msg.method === "prev") && data.file !== undefined) {
        bridge.send({ type: "position", file: data.file, line: data.line ?? 0 });
      }
    } catch (err) {
      bridge.send({ type: "error", message: String(err) });
    } finally {
      bridge.send({ type: "rpc_end", method: msg.method });
    }
    return;
  }
});
