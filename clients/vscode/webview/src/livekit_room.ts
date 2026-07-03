// clients/vscode/webview/src/livekit_room.ts
import { Room, RoomEvent, Track, RemoteParticipant } from "livekit-client";
import { AudioPlayer } from "./audio_player";
import type { WebviewToHost } from "./message_bridge";

type SendFn = (msg: WebviewToHost) => void;

export class LiveKitRoom {
  private _room: Room;
  private _player: AudioPlayer;
  private _agentIdentity: string | null = null;

  constructor(private readonly _send: SendFn) {
    this._room = new Room();
    this._player = new AudioPlayer();
  }

  async connect(url: string, token: string): Promise<void> {
    this._room.on(
      RoomEvent.TrackSubscribed,
      (track, _pub, participant: RemoteParticipant) => {
        this._agentIdentity = participant.identity;
        if (track.kind === Track.Kind.Audio) {
          this._player.attachTrack(track.mediaStreamTrack);
        }
      },
    );

    this._room.on(RoomEvent.Disconnected, (reason) => {
      this._send({ type: "disconnected", reason: String(reason) });
      this._player.stop();
    });

    await this._room.connect(url, token);
    this._send({ type: "connected", participantId: this._room.localParticipant.sid });
  }

  async performRpc(method: string, payload: object): Promise<string> {
    if (!this._agentIdentity) {
      throw new Error("Breakdown agent is not connected yet.");
    }
    return this._room.localParticipant.performRpc({
      destinationIdentity: this._agentIdentity,
      method,
      payload: JSON.stringify(payload),
      responseTimeout: 15000,
    });
  }

  async disconnect(): Promise<void> {
    await this._room.disconnect();
    this._player.stop();
    this._agentIdentity = null;
  }
}
