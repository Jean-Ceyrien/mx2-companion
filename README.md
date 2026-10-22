# MX2 Companion

A Mac companion for using the Traktor MX2 with djay Pro. Choose the app for its Native and MIDI modes, or run the original MIDI bridge from Terminal. This release does not include a complete standalone djay mapping for the physical MX2.

**[Open the website](docs/index.html)** · **[Mac app](docs/downloads/MX2-Companion-0.5.0-macOS-arm64.dmg)** · **[Classic MIDI package](docs/downloads/MX2-Classic-MIDI-0.5.0.zip)**

## Install the Mac app

1. Open the DMG and drag MX2 Companion into Applications.
2. Connect the MX2, choose Native or MIDI in Companion, and start the connection.
3. Import the matching mapping in djay and select the virtual `MX2 for djay` device.

The downloadable app is for Apple silicon Macs.
This build is not notarized by Apple. If macOS blocks the first launch, follow [Apple's Open Anyway steps](https://support.apple.com/en-ie/102445) after trying to open it.

## Use Classic MIDI without the app

1. Download and unzip the [Classic MIDI package](docs/downloads/MX2-Classic-MIDI-0.5.0.zip).
2. Switch the MX2 to MIDI mode and run `DEMARRER-MX2.command`. Keep its Terminal window open.
3. Import `Traktor MX2 - Visual Complete.djayMidiMapping` in djay, select the virtual `MX2 for djay` device, and disable djay's direct `Traktor MX2` MIDI input.

The package contains the original 293-action mapping, MIDI bridge and full setup guide. This is the pre-app configuration previously checked on both decks. The mapping file alone does not provide a complete direct MX2 mapping: it needs the bridge for SHIFT, pad modes and feedback.

## Website

The English site is in `docs/`. The GitHub Actions workflow deploys it through GitHub Pages from the `main` branch after Pages is enabled in repository settings.

MX2 Companion is a community project. Traktor MX2 is a Native Instruments product, and djay is an Algoriddim product. See [notices](NOTICES.md).

## License and source code

Copyright (C) 2026 Jean-Ceyrien and contributors. Original project code is licensed under **GNU GPL version 3 only (GPL-3.0-only)**, without warranty. See [LICENSE](LICENSE) and [licensing scope](LICENSING.md). Third-party components and assets retain their own terms.

**[Browse the 0.5.0 source](source/)** · **[Download the corresponding source](docs/downloads/MX2-Companion-0.5.0-source.zip)**

The source kit includes the application, Classic MIDI bridge, Swift transports, mappings, interface resources, tests and build instructions. See [source README](source/README.md). Runtime sources match the archived release; packaging and licensing were updated on 22 October 2026.
