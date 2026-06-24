// clients/vscode/webview/src/audio_player.ts

export class AudioPlayer {
  private _context: AudioContext | null = null;

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
      ctx.resume();
    }
  }

  stop(): void {
    this._context?.close();
    this._context = null;
  }
}
