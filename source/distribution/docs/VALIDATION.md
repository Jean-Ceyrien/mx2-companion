# Validation and limitations

This document records the scope of the integration, rather than a claim that every machine or combination is supported.

## Hardware-tested development setup

- macOS, with a Native Instruments Traktor MX2 connected by USB.
- djay Pro 5.6.9.
- Native HID bridge, virtual MIDI endpoint `MX2 for djay`, mapping `Traktor MX2 - Native RGB`.
- 293 control action rows preserved from the calibrated mapping, plus two deck-meter and two end-warning outputs.
- The visual calibration recorded 116 distinct controls, with no duplicate physical MIDI addresses.

The following checks were confirmed by the operator on both decks unless a narrower scope is stated:

| Family | Confirmed behavior |
|---|---|
| Transport | PLAY/CUE operate their own deck; SYNC works with roles reversed |
| Jogs | Touch, rotate, release, direction/speed and SHIFT seek; native input check confirmed operation |
| Mixer | Own-channel volume, normal EQ, crossfader; gain audibly changes the correct track |
| Tempo | Both faders change the owning BPM progressively and return to original tempo at center |
| Library | BROWSE selection and press-to-load on the owning paused deck |
| Headphones | Manual A-only/B-only preview and corresponding lights; main channels 1–2 and preview 3–4 |
| HOTCUES | All eight pads create/return to cues; SHIFT clear tested with one disposable cue per deck |
| STEMS | All eight mute/solo pads; second press restores the part or full mix |
| PATTERN | All eight occupied sample slots; SHIFT stop tested with one sample per deck |
| FLUX LOOP | All eight held durations release correctly; SHIFT persistent one-beat loop tested on pad 6 |
| Deck FX | Slot buttons/parameters for FX1–FX3 and SHIFT next-effect selection |
| Mixer FX | FILTER, FX1–FX3 enable/Wet-Dry routing independently on each channel |
| FX4 | Operator found that djay HOLD must be off for apply-while-held/release-to-stop behavior |
| Loop encoders | SIZE/autoloop behavior; isolated SHIFT + left encoder tests confirm moving a loop without changing duration on A and B; SHIFT + right rotation changes beatjump interval |
| RGB/feedback | Playback/headphone/mode states, mode-colored pads, moving meters, green loop shell, red end warning and return to blue independently on both sides |
| USB reconnect | Controls/lights recover while bridge and djay remain open; some knobs need repositioning |
| djay restart | Controls, jogs, and lights recover without reselecting mapping while bridge remains open |

The original development suite had 38 passing software checks for mapping contracts, decoding, routing, releases, feedback, and transport behavior. This historical count is not the current release test count; use the release build report for new packaging and platform checks. Automated tests cannot replace controller, audio, or app routing checks.

## MIDI mode in Companion 0.5.0

The previously validated CoreMIDI bridge and 293-row Visual Complete mapping are selectable in the Mac app. The packaged MIDI transport self-test and bridge lifecycle have automated checks. Physical controller and djay routing in this new packaged version still need a manual recheck; the historical MIDI mapping validation does not prove the packaged app on every Mac. Native mode remains available.

## Known limits

- Windows has not been physically tested. Supplying Windows source/build support does not establish working djay routing, HID permissions, RGB feedback, audio drivers, or installation.
- A single macOS test setup does not establish compatibility with every Mac architecture, OS version, or newer djay release. Inspect the build's architecture and deployment target.
- Some secondary actions and SHIFT variants remain implemented but not individually exercised: library shortcuts, loop in/out, key/master/quantize/slip/reverse variants, all-FX macros, channel FX assignment buttons, microphone, and all eight shifted-pad variants.
- Gain was audibly confirmed on its own deck. djay documents that hardware and on-screen gain can be independent; a stationary on-screen knob alone is not a mapping failure.
- Individual hotcue colors are not implemented. Pads indicate their bank and state using the bridge's palette.
- The bridge uses 7-bit MIDI control values after decoding HID; it does not preserve full native analog resolution through djay.
- No pickup/soft takeover is implemented in the bridge. Potentiometers can need repositioning after reconnect.
- PATTERN is djay sampler playback, not Traktor's step sequencer. FX4 amount is a filter fallback, not a continuous instant-effect parameter.
- The main clip light has no validated feedback source. Internal button 82 is unidentified and unmapped.
- djay features depend on the user's installed version and available functionality. Audio routing and microphone input settings are configured in djay, not by the mapping.

## Windows release gate

Before calling a Windows build supported, test and record:

1. Installation/launch on a clean Windows machine, including the required MIDI and audio drivers.
2. Native HID access to the correct MX2 interface without changing or replacing its audio/MIDI driver.
3. A single loopMIDI bus named exactly `MX2 for djay`, exposing matching input/output names. Confirm djay actually delivers feedback through this virtual bus. The Windows-specific mapping reserves channels 10–14 (zero-based) for feedback, separate from input channels 0–9 and 15; confirm that the transport ignores echoed input messages and no feedback retriggers controls.
4. Mapping import and selection, and prevention of duplicate input from the raw MX2 endpoint.
5. Bilateral PLAY/CUE, jog touch/release and speed/direction, analog endpoints, SHIFT independence, held-pad release, all pad banks, effects, and audio preview.
6. Meter and end-warning feedback, RGB bank colors, loop lights, and no MIDI feedback loop.
7. USB reconnect, djay restart, app Stop/Start, and a second-launch attempt, with no stuck notes or duplicated ports.

## Recheck a shared release

On a recipient's machine, start with paused tracks and a moderate volume. Check PLAY/CUE on A/B, scratch touch/release, headphone preview, and one held loop per deck before a longer session. Check reconnect and restart recovery. Report the app version, operating system, djay version, selected mapping and port names, plus the exact control/gesture and observed result. Share diagnostics only after reviewing them; personal session logs are not part of the distribution archive.

## Version0.2 desktop interface and passive monitor

The integrated MX2 Companion window, new icon, guided setup and offline 116-control atlas have been observed on the development Mac. Native mode is confirmed inside the app while the bridge is stopped. A real CoreMIDI inventory test showed zero extra virtual sources with the passive observer alone, one source with the bridge running alongside it, and zero sources after shutdown. The integrated Start action reached ready/native state with djay feedback and zero decoder errors.

The full development suite passes 78 checks, and the curated source suite passes 60. MIDI mode was observed in the app after the physical mode toggle, and the user confirmed Native mode after switching back. Monitoring remained active while the bridge was stopped. Windows remains unverified.

## Companion 0.3 regression checks

The new compact desktop window was opened on the development Mac. The native bridge reached ready state with feedback and zero decoder errors. Clicking Mapping installed returned an already-installed message without opening djay or importing another copy. Status continued refreshing after that action. The full development suite passes 78 tests; the curated source suite passes 60.

A user reported crossfader movement during touched jog rotation after mapping import. A passive CoreMIDI capture observed 941 virtual jog CC messages and no crossfader CC messages during the gesture. Crossfader Cutting Mode was confirmed disabled in persisted djay preferences, and a new mapping identity with identical bindings did not resolve the report. The user confirmed the central crossfader was affected. After quitting and reopening djay with Companion kept running, the user confirmed that the crossfader remained stable during touched jog rotation. Restarting djay cleared the observed issue; the exact internal cause is not established. First-import guidance now includes that restart.

## GAIN and MAIN follow-up, 18 October 2026

The physical MAIN knob was swept from minimum to midpoint. Native ADC values 3–1999 decoded to virtual channel 16 CC 32 values 0–62. The Main Volume slider in djay 5.6.9 reached 0.488188982 (62/127), confirming that the physical control reaches the software master. The user subsequently reported that everything was fine; the exact listening output was not specified. Headphone CUE preview is a separate route.
