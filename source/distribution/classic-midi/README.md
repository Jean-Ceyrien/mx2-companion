# MX2 Classic MIDI for djay Pro

This is the working MIDI setup used before MX2 Companion was packaged as an app. It uses the original **Visual Complete** djay mapping and a small CoreMIDI bridge started from Terminal. No MX2 Companion app is required.

## Setup

1. Unzip the package to a writable folder on an Apple silicon Mac. Keep its folders together.
2. Connect the Traktor MX2 and switch it to MIDI mode. Press both physical SHIFT buttons together once if needed.
3. Double-click `DEMARRER-MX2.command` and keep its Terminal window open while using djay. If macOS blocks the launcher, open Terminal in this folder and run `zsh DEMARRER-MX2.command`.
4. Open `mappings/Traktor MX2 - Visual Complete.djayMidiMapping` and confirm the import in djay Pro.
5. In djay's MIDI settings, select **MX2 for djay** with the **Traktor MX2 - Visual Complete** configuration. Disable djay's direct **Traktor MX2** MIDI input to avoid duplicate commands.
6. In djay's audio settings, choose MX2 channels 1–2 for Main and 3–4 for headphone cue.

The Terminal launcher creates the virtual **MX2 for djay** MIDI ports and keeps the controller's deck modes, SHIFT layers, pad banks and feedback in sync. The mapping has 293 actions. The configuration was used and physically checked on both decks before the desktop app was created; representative transport, jog, cue, mixer, library, pad, FX and light behavior was confirmed. That history does not guarantee every control on every computer.

To stop, close the Terminal window or press Control-C. Quit the MIDI bridge before starting Companion, since both use the same controller and virtual port.

## Included files

- `DEMARRER-MX2.command` — original Terminal launcher.
- `mappings/Traktor MX2 - Visual Complete.djayMidiMapping` — validated djay mapping.
- `tools/` and `evidence/midi-profile.json` — MIDI bridge runtime and measured control profile.

This bundle targets macOS on Apple silicon. It needs the built-in Python 3 runtime and no extra Python packages.
The included transport is not notarized by Apple. If macOS blocks it on first launch, use System Settings → Privacy & Security → Open Anyway after the launch attempt, following [Apple's instructions](https://support.apple.com/en-ie/102445).
