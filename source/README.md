# MX2 Companion

Use a Traktor MX2 with djay Pro on Mac. Companion offers Native and MIDI modes, a guided setup, a searchable control reference and 293 mapping actions. The original Classic MIDI package runs the validated pre-app bridge from Terminal.

**[View the website](https://jean-ceyrien.github.io/mx2-companion/)** · **[Download the Mac installer](https://jean-ceyrien.github.io/mx2-companion/downloads/MX2-Companion-0.5.0-macOS-arm64.dmg)** · **[Download Classic MIDI](https://jean-ceyrien.github.io/mx2-companion/downloads/MX2-Classic-MIDI-0.5.0.zip)**

## Install Companion

1. Open the DMG and drag MX2 Companion into Applications.
2. Connect the MX2, choose Native or MIDI in Companion, then start the connection.
3. Import the matching mapping in djay. Select the virtual `MX2 for djay` device and disable the physical Traktor MX2 input to avoid duplicate commands.
4. Set main audio to MX2 channels 1–2 and headphone monitoring to 3–4.

The Mac installer targets Apple silicon. Windows source is included for testing but is not a validated release.

## Classic MIDI without Companion

Use [the Classic MIDI package](distribution/classic-midi/README.md) for the pre-app setup. Run the included Terminal launcher, import Visual Complete, and select the virtual `MX2 for djay` device in djay. Keep the launcher open while mixing. The mapping depends on its MIDI bridge for SHIFT, pad banks and feedback.

## Build and test

Build on macOS with `distribution/BUILD-MAC.command` (Python 3.12 and Xcode command-line tools). To create the DMG, run `python distribution/build_dmg.py` after the app build. Windows build instructions are in `distribution/BUILD-WINDOWS.ps1`.

Run `python3 -m unittest discover -s tools -p 'test_*.py'` for hardware-free checks. See [validation and limitations](distribution/docs/VALIDATION.md) for physical test scope and [third-party notices](distribution/docs/THIRD-PARTY-NOTICES.md) for dependencies and image attribution.

## Website

The static site is in `docs/`. The included GitHub Pages workflow publishes it from `main` after Pages is enabled for the repository.

## License and corresponding source

Copyright (C) 2026 Jean-Ceyrien and contributors. Original project code is licensed under GNU GPL version 3 only (GPL-3.0-only). You may modify and redistribute it under that license; there is no warranty. See [LICENSE](LICENSE), [licensing scope](LICENSING.md) and the third-party notices.

This source kit includes the Python and Swift sources, mappings, interface resources and build scripts for Companion 0.5.0 and Classic MIDI 0.5.0. The public release sources are the archived runtime sources; licensing and packaging were updated on 22 October 2026. Build on the target operating system. No controller, proprietary DJ application, credentials or personal session logs are included.

For exact macOS build dependency versions and upstream source locations, see [dependency versions](distribution/requirements-macos-lock.txt) and [upstream sources](distribution/UPSTREAM-SOURCES.md). [Release source checks](SOURCE-MANIFEST.json) record the correspondence checks.
