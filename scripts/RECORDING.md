# How to Record the README Demo

This document ensures the demo can be reproduced when the UI changes.

## Setup

- VS Code theme: Default Light+ (most legible in small GIFs)
- Font: Cascadia Code, size 14
- Terminal: VS Code integrated terminal
- Demo file: `examples/minimal_agent.py` (visible in the recording)
- Window size: 1280x720

## VS Code Settings for Recording

```json
{
  "editor.fontSize": 14,
  "editor.fontFamily": "Cascadia Code",
  "workbench.colorTheme": "Default Light+",
  "editor.minimap.enabled": false,
  "breadcrumbs.enabled": false
}
```

## Script

1. Open `examples/minimal_agent.py` in VS Code.
2. Click line 8 (the `async def entrypoint` line).
3. Press `Cmd+K Cmd+E` to start the session.
4. Wait for the audio to start (status bar changes to "explaining").
5. Press `Cmd+K Cmd+N` three times to advance through lines.
6. Hold `Cmd+K Cmd+Space` and say "what does this parameter do?".
7. Wait for the AI to answer.
8. Press `Cmd+K Cmd+Q` to stop.

## Export

- Record at 1280x720 using Kap (macOS) or OBS (all platforms).
- Export as GIF, max 5MB, using Gifski for quality compression.
- Export as MP4 at 1080p for the linked full-quality version.
- Place GIF at `docs/demo.gif` and link it from README.md.

## Duration

Target: 25-35 seconds total. Cut anything over 40 seconds.
