# MX2 Companion

A Mac companion for using the Traktor MX2 with djay Pro. Choose the app for its Native and MIDI bridge modes, or use the separate Direct MIDI mapping without the app.

**[Open the website](docs/index.html)** · **[Mac app](docs/downloads/MX2-Companion-0.5.0-macOS-arm64.dmg)** · **[Direct MIDI mapping](docs/downloads/MX2-Direct-MIDI-Mapping-0.5.0.zip)**

## Install the Mac app

1. Open the DMG and drag MX2 Companion into Applications.
2. Connect the MX2, choose Native or MIDI in Companion, and start the connection.
3. Import the matching mapping in djay and select the virtual `MX2 for djay` device.

The downloadable app is for Apple silicon Macs.
This build is not notarized by Apple. If macOS blocks the first launch, follow [Apple's Open Anyway steps](https://support.apple.com/en-ie/102445) after trying to open it.

## Use MIDI without the app

1. Download and unzip the [Direct MIDI package](docs/downloads/MX2-Direct-MIDI-Mapping-0.5.0.zip).
2. Switch the MX2 to MIDI mode and open `Traktor MX2 - Direct MIDI.djayMidiMapping` in djay.
3. Select the physical `Traktor MX2` device and the Direct MIDI mapping. Keep Companion and other MX2 bridges stopped.

The package contains the full setup guide. The 105-action direct configuration has passed file checks but has not yet been tested with the controller and djay. It omits SHIFT layers, alternate pad banks, RGB lights and meters.

## Website

The English site is in `docs/`. The GitHub Actions workflow deploys it through GitHub Pages from the `main` branch after Pages is enabled in repository settings.

MX2 Companion is a community project. Traktor MX2 is a Native Instruments product, and djay is an Algoriddim product. See [notices](NOTICES.md).
