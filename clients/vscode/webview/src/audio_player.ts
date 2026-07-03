// clients/vscode/webview/src/audio_player.ts
import type { RemoteTrack } from "livekit-client";

export class AudioPlayer {
  private _elements: HTMLAudioElement[] = [];

  // RemoteTrack.attach() is livekit-client's own built-in playback method —
  // it creates and manages an <audio> element internally, which goes
  // through the browser's standard media pipeline. Autoplay is expected to
  // fail here until Room.startAudio() is called from a real user gesture
  // (see LiveKitRoom); that's the SDK's own documented recovery path, not
  // an error condition to retry manually.
  attachTrack(track: RemoteTrack): void {
    const el = track.attach();
    document.body.appendChild(el);
    this._elements.push(el);
  }

  stop(): void {
    for (const el of this._elements) {
      el.pause();
      el.remove();
    }
    this._elements = [];
  }
}
