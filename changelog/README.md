# Changelog Fragments

Add one file per pull request in this directory. Do not edit `CHANGELOG.md` directly.

## Naming

`<PR_NUMBER>.<type>.md`

Types:
- `feature` -- new feature
- `bugfix` -- bug fix
- `doc` -- documentation change
- `removal` -- deprecated feature removed
- `misc` -- maintenance, dependency update, refactor

## Content

One sentence describing the change from the user's perspective.

## Example

File: `changelog/42.feature.md`
Content: `Add ElevenLabs TTS provider support via TTS_PROVIDER=elevenlabs.`

## How Releases Work

The release workflow runs `towncrier build` which compiles all fragments into
`CHANGELOG.md` and deletes the individual files.
