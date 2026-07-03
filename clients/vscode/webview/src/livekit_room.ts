// clients/vscode/webview/src/livekit_room.ts
import { Room, RoomEvent, Track, RemoteParticipant, RpcError } from "livekit-client";
import { AudioPlayer } from "./audio_player";
import type { WebviewToHost } from "./message_bridge";

type SendFn = (msg: WebviewToHost) => void;

export class LiveKitRoom {
  private _room: Room;
  private _player: AudioPlayer;
  private _agentIdentity: string | null = null;
  private _agentIdentityWaiters: Array<(identity: string) => void> = [];

  constructor(private readonly _send: SendFn) {
    this._room = new Room();
    this._player = new AudioPlayer();
  }

  private _setAgentIdentity(identity: string): void {
    if (this._agentIdentity) {
      return;
    }
    this._agentIdentity = identity;
    for (const resolve of this._agentIdentityWaiters) {
      resolve(identity);
    }
    this._agentIdentityWaiters = [];
  }

  // Job dispatch on the agent side is asynchronous and can take a few
  // seconds after this client's own room connection succeeds, so the agent
  // participant may not have joined yet even though we're "connected."
  // Wait briefly rather than failing immediately on the first RPC call.
  private _waitForAgentIdentity(timeoutMs: number): Promise<string> {
    if (this._agentIdentity) {
      return Promise.resolve(this._agentIdentity);
    }
    return new Promise((resolve, reject) => {
      const onIdentity = (identity: string): void => {
        clearTimeout(timer);
        resolve(identity);
      };
      const timer = setTimeout(() => {
        const idx = this._agentIdentityWaiters.indexOf(onIdentity);
        if (idx !== -1) {
          this._agentIdentityWaiters.splice(idx, 1);
        }
        reject(new Error("Breakdown agent did not join the room in time."));
      }, timeoutMs);
      this._agentIdentityWaiters.push(onIdentity);
    });
  }

  async connect(url: string, token: string): Promise<void> {
    // The agent joins the room (and is targetable via performRpc) as soon as
    // it connects — well before it ever publishes an audio track, which only
    // happens the first time it speaks. Capturing identity from
    // TrackSubscribed alone would deadlock the very first RPC call.
    this._room.on(RoomEvent.ParticipantConnected, (participant: RemoteParticipant) => {
      this._setAgentIdentity(participant.identity);
    });

    this._room.on(
      RoomEvent.TrackSubscribed,
      (track, _pub, participant: RemoteParticipant) => {
        this._setAgentIdentity(participant.identity);
        if (track.kind === Track.Kind.Audio) {
          this._player.attachTrack(track);
        }
      },
    );

    this._room.on(RoomEvent.Disconnected, (reason) => {
      this._send({ type: "disconnected", reason: String(reason) });
      this._player.stop();
    });

    this._room.on(RoomEvent.AudioPlaybackStatusChanged, () => {
      console.log("[breakdown] audio: canPlaybackAudio =", this._room.canPlaybackAudio);
    });

    await this._room.connect(url, token);

    // Defensive: pick up a participant that joined before this client
    // finished connecting, in case ParticipantConnected isn't replayed.
    for (const participant of this._room.remoteParticipants.values()) {
      this._setAgentIdentity(participant.identity);
      break;
    }

    this._send({ type: "connected", participantId: this._room.localParticipant.sid });
  }

  // Room.startAudio() is livekit-client's documented recovery path for
  // browser-blocked autoplay — it retries every <audio> element the SDK
  // created via track.attach(). Exposed here so a page-level gesture
  // listener (registered once in index.ts, independent of reconnects) can
  // call it against whichever room is currently active.
  startAudio(): Promise<void> {
    return this._room.startAudio();
  }

  async performRpc(method: string, payload: object): Promise<string> {
    // Cold job dispatch (spawning the agent's worker process, opening its
    // vector index, joining the room) has been observed to take 25-30s
    // under load — 10s was too tight and failed real, successful startups.
    const identity = await this._waitForAgentIdentity(45000);
    const params = {
      destinationIdentity: identity,
      method,
      payload: JSON.stringify(payload),
      responseTimeout: 15000,
    };
    try {
      return await this._room.localParticipant.performRpc(params);
    } catch (err) {
      // The very first RPC call right after connecting has been observed
      // to time out because the reliable data channel is still finishing
      // negotiation (concurrent with the agent's audio track attaching) —
      // not a real failure. One retry consistently succeeds once the
      // channel has settled; only retry that specific, transient case.
      if (
        err instanceof RpcError &&
        (err.code === RpcError.ErrorCode.RESPONSE_TIMEOUT ||
          err.code === RpcError.ErrorCode.CONNECTION_TIMEOUT)
      ) {
        console.warn("[breakdown] performRpc timed out, retrying once:", err);
        return await this._room.localParticipant.performRpc(params);
      }
      throw err;
    }
  }

  async disconnect(): Promise<void> {
    await this._room.disconnect();
    this._player.stop();
    this._agentIdentity = null;
  }
}
