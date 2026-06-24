// clients/vscode/webview/src/livekit_room.ts
import {
  Room,
  RoomEvent,
  Track,
  RemoteTrackPublication,
  RemoteParticipant,
  DataPacket_Kind,
} from "livekit-client";
import { AudioPlayer } from "./audio_player";
import type { WebviewToHost } from "./message_bridge";

type SendFn = (msg: WebviewToHost) => void;

export class LiveKitRoom {
  private _room: Room;
  private _player: AudioPlayer;

  constructor(private readonly _send: SendFn) {
    this._room = new Room();
    this._player = new AudioPlayer();
  }

  async connect(url: string, token: string): Promise<void> {
    this._room.on(RoomEvent.TrackSubscribed, (track, _pub, _participant) => {
      if (track.kind === Track.Kind.Audio) {
        this._player.attachTrack(track.mediaStreamTrack);
      }
    });

    this._room.on(RoomEvent.Disconnected, (reason) => {
      this._send({ type: "disconnected", reason: String(reason) });
      this._player.stop();
    });

    this._room.on(RoomEvent.DataReceived, (payload, _participant, _kind) => {
      try {
        const msg = JSON.parse(new TextDecoder().decode(payload));
        if (msg.type === "transcript") {
          this._send({ type: "transcript", text: msg.text, final: msg.final });
        } else if (msg.type === "status") {
          this._send({ type: "status", state: msg.state });
        }
      } catch {
        // ignore malformed packets
      }
    });

    await this._room.connect(url, token);
    this._send({ type: "connected", participantId: this._room.localParticipant.sid });
  }

  async sendData(payload: object): Promise<void> {
    const data = new TextEncoder().encode(JSON.stringify({ v: 1, ...payload }));
    await this._room.localParticipant.publishData(data, { reliable: true });
  }

  async publishMicTrack(track: MediaStreamTrack): Promise<void> {
    await this._room.localParticipant.publishTrack(track);
  }

  async disconnect(): Promise<void> {
    await this._room.disconnect();
    this._player.stop();
  }
}
