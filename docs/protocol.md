# Protocol Specification v1

This document is the authoritative reference for the message protocol between
a Breakdown platform client and the Python core agent.

## Connection Flow

1. Read `.breakdown/runtime.json` -- contains `port` and `livekit_url`.
2. `GET http://127.0.0.1:<port>/token?room=<room_name>` -- returns `{"token": "...", "url": "..."}`.
3. Connect to the LiveKit room using the token.
4. Begin sending and receiving DataPackets.

## Room Name

```
room_name = "breakdown-" + sha256(absolute_workspace_root)[:12]
```

The room name is deterministic. The same workspace root always produces the same room name.

## Packet Envelope

All DataPackets are UTF-8 encoded JSON with this envelope:

```json
{ "v": 1, "type": "<type>", ...additional fields }
```

If `v` is not `1`, show an error and ask the user to update Breakdown.

## Client to Agent

### explain

```json
{ "v": 1, "type": "explain", "file": "src/foo.py", "line": 42 }
```

`file` must be relative to the workspace root. `line` is 1-indexed.

### next / prev

```json
{ "v": 1, "type": "next" }
{ "v": 1, "type": "prev" }
```

### stop

```json
{ "v": 1, "type": "stop" }
```

## Agent to Client

### status

```json
{ "v": 1, "type": "status", "state": "explaining" }
```

States: `idle`, `explaining`, `listening`, `interrupted`

### position

```json
{ "v": 1, "type": "position", "file": "src/foo.py", "line": 43 }
```

### transcript

```json
{ "v": 1, "type": "transcript", "text": "what does this do", "final": true }
```

`final: false` for partial STT results; `final: true` for the committed transcription.

### error

```json
{
  "v": 1,
  "type": "error",
  "code": "PROVIDER_RATE_LIMITED",
  "message": "OpenAI rate limit reached. Retrying in 5 seconds.",
  "recoverable": true,
  "retry_after_ms": 5000
}
```

Error codes: `PROVIDER_RATE_LIMITED`, `INDEX_EMPTY`, `STT_FAILED`, `ROOM_DISCONNECTED`

When `recoverable` is `true`, show a non-blocking notification and wait.
When `recoverable` is `false`, show a blocking error and offer to restart the session.

## Audio

The agent publishes a LiveKit audio track. Clients subscribe to it and play it
using whatever audio API is available on their platform. Audio is not sent as
DataPackets.
