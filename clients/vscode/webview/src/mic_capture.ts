// clients/vscode/webview/src/mic_capture.ts

export class MicCapture {
  private _stream: MediaStream | null = null;
  private _track: MediaStreamTrack | null = null;

  async start(): Promise<MediaStreamTrack | null> {
    try {
      this._stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
        video: false,
      });
      this._track = this._stream.getAudioTracks()[0] ?? null;
      return this._track;
    } catch (err) {
      console.error("Mic access denied:", err);
      return null;
    }
  }

  stop(): void {
    this._stream?.getTracks().forEach((t) => t.stop());
    this._stream = null;
    this._track = null;
  }

  get track(): MediaStreamTrack | null {
    return this._track;
  }
}
