// clients/vscode/webview/src/audio_player.ts

export class AudioPlayer {
  private _context: AudioContext | null = null;

  constructor() {
    // Browsers refuse to start/resume an AudioContext outside a real user
    // gesture fired inside this document — focusing the sidebar view
    // programmatically (ChatViewProvider.connect()'s `${VIEW_ID}.focus`)
    // does not count. Unlock on the first genuine interaction with the
    // panel so narration audio isn't silently dropped.
    const unlock = (): void => {
      void this._getContext().resume();
    };
    document.addEventListener("pointerdown", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });
  }

  private _getContext(): AudioContext {
    if (!this._context) {
      this._context = new AudioContext();
    }
    return this._context;
  }

  attachTrack(track: MediaStreamTrack): void {
    const ctx = this._getContext();
    const stream = new MediaStream([track]);
    const source = ctx.createMediaStreamSource(stream);
    source.connect(ctx.destination);
    if (ctx.state === "suspended") {
      void ctx.resume();
    }
  }

  stop(): void {
    this._context?.close();
    this._context = null;
  }
}
