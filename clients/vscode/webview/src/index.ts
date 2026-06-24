// clients/vscode/webview/src/index.ts
import { createBridge, type HostToWebview } from "./message_bridge";
import { LiveKitRoom } from "./livekit_room";
import { MicCapture } from "./mic_capture";

const bridge = createBridge();
const mic = new MicCapture();
let room: LiveKitRoom | null = null;

bridge.send({ type: "ready" });

bridge.onMessage(async (msg: HostToWebview) => {
  if (msg.type === "connect") {
    room = new LiveKitRoom(bridge.send);
    try {
      await room.connect(msg.url, msg.token);
      const track = await mic.start();
      if (track) {
        await room.publishMicTrack(track);
      }
    } catch (err) {
      bridge.send({ type: "error", message: String(err) });
    }
    return;
  }

  if (msg.type === "disconnect") {
    await room?.disconnect();
    mic.stop();
    room = null;
    return;
  }

  if (msg.type === "send_data") {
    await room?.sendData(msg.payload);
    return;
  }
});
