# Building a Breakdown Platform Client

This document specifies what a thin client must implement to work with the
Breakdown Python core. You do not need to understand the core internals.

## What a Client Does

1. Read `.breakdown/runtime.json` to find the token server port.
2. Call `GET http://127.0.0.1:<port>/token?room=breakdown-<hash>` to get a JWT.
3. Connect to the LiveKit room using the JWT and the `livekit_url` from the response.
4. Send DataPackets to the agent (commands).
5. Receive DataPackets from the agent (status, position, transcript, error).
6. Play the TTS audio track published by the agent (via the platform's audio API).
7. Optionally capture mic audio and publish it as a track for STT.

## Room Name

The room name is deterministic based on the workspace root:

```
sha256(absolute_workspace_root_path)[:12]
room_name = "breakdown-" + hash
```

## DataPacket Schema (Protocol v1)

All packets are JSON with envelope: `{ "v": 1, "type": "<type>", ...fields }`

### Client -> Agent

| type | required fields | meaning |
|---|---|---|
| `explain` | `file` (string, relative path), `line` (integer, 1-indexed) | Explain this line |
| `next` | none | Move to next line |
| `prev` | none | Move to previous line |
| `stop` | none | End the session |

### Agent -> Client

| type | fields | meaning |
|---|---|---|
| `status` | `state`: `"idle"/"explaining"/"listening"/"interrupted"` | State changed |
| `position` | `file` (string), `line` (integer) | Current position updated |
| `transcript` | `text` (string), `final` (boolean) | STT result (partial or final) |
| `error` | `code` (string), `message` (string), `recoverable` (boolean), `retry_after_ms` (integer) | Error occurred |

### Error Codes

| code | meaning | recoverable |
|---|---|---|
| `PROVIDER_RATE_LIMITED` | API rate limit hit | true |
| `INDEX_EMPTY` | No index found; run `breakdown index` | false |
| `STT_FAILED` | Speech transcription failed | true |
| `ROOM_DISCONNECTED` | LiveKit room connection lost | true |

## Important Rules

- Paths in `explain` packets must be relative to the workspace root. Never send absolute paths.
- The client is responsible for audio playback. The agent publishes a LiveKit audio track.
- Protocol version is in the `v` field. If `v` does not equal `1`, show an error asking
  the user to update both the core and the client.

## Implementation Checklist

- [ ] Read runtime.json and get token
- [ ] Connect to LiveKit room
- [ ] Send `explain` packet on line selection
- [ ] Send `next` / `prev` on navigation
- [ ] Receive and display `status` updates
- [ ] Play the agent's audio track
- [ ] Handle `error` packets (show notification for `recoverable: true`, block UI for `false`)
- [ ] Send `stop` on session end / plugin deactivation
- [ ] Kill the Python core process on deactivation (if the client started it)
