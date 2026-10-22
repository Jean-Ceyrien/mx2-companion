# MX2 Companion

Use a Native Instruments Traktor MX2 with djay through the companion bridge and its mapping. The bridge handles the controls, touch-sensitive jog wheels, pad banks, and RGB lights. djay handles playback and audio.

The mapping contains **293 action rows**, plus four dedicated meter/end-warning outputs. That count includes SHIFT actions and intentional effect macros; it is not a count of hardware buttons. A mapping file alone cannot provide this integration: keep the bridge running while you use djay.

The native integration has been physically tested on macOS with djay 5.6.9 and an MX2. The Windows implementation requires separate validation; see [Validation and limitations](VALIDATION.md). This is a community integration, not an official Native Instruments or Algoriddim product.

## First setup on Mac

1. Connect the MX2 by USB. Close other controller bridges and Traktor so that only this bridge controls the MX2.
2. Open **MX2 Companion.app**, then click **Start connection**. Keep the app open while mixing.
3. Choose **Native** or **MIDI** in Companion and use that mode on the MX2. If the app reports a different mode, press the two physical SHIFT buttons together once, then move a control to confirm. Do not repeatedly switch modes. Pressing both SHIFT buttons together is a hardware mode switch, not a DJ command. Stop the bridge before changing the selection in Companion.
4. Click **Install djay mapping** and confirm the import in djay. Select the virtual device **MX2 for djay** and the configuration **Traktor MX2 - Native RGB** for Native or **Traktor MX2 - Visual Complete** for MIDI in djay's MIDI settings. The button opens the supplied file for djay to import; it does not silently replace files in your mapping folder.
5. Disable djay's direct MIDI connection to **Traktor MX2** if it is enabled. Use the virtual device for controls to avoid duplicate actions.
6. In djay's audio device settings, choose MX2 channels **1–2 for the main output** and **3–4 for headphone monitoring**, then apply the settings. These settings are separate from the MIDI mapping.
7. Load a track on each deck. Check PLAY and CUE on each side, then turn the volume up gradually.

The MIDI choice uses the original CoreMIDI bridge and Visual Complete mapping. Native retains the RGB HID bridge. Only one bridge can run at a time; Stop & quit closes the selected bridge.

The Mac package targets **Apple silicon (arm64), macOS 11 or later** and includes its Python runtime, web interface and native transport. You do not need to install Python or use Terminal. Intel Macs need a separately built and tested package. If macOS displays a security message for an unsigned build, review the source and the release you downloaded before using the system's **Open Anyway** option. Signing status is recorded in the release notes.

For later sessions, connect the MX2, open the app, and click **Start connection**. djay should remember the installed mapping. **Stop & quit** shows the shutdown progress while the bridge and device monitor stop, then closes Companion. Do not run the older Terminal bridge at the same time.

## Hear a different track in your headphones

Plug your headphones into the MX2. In djay's monitoring panel, turn automatic deck selection off. Set **CUE MIX toward CUE**, and set **CUE VOL** to a moderate level. Enable the small headphone button for the deck you want to preview; disable it for the other deck.

At the MIX end of CUE MIX, the headphones play the main output. In the middle they blend the preview and main outputs. If you only hear the live track, check both this knob and the channels 3–4 monitor assignment.

## Windows setup: testing required

The Windows source and build instructions are provided for testing. They are not a verified, ready-to-use Windows release yet. The executable must be built on Windows using the supplied PowerShell build process. Native HID access, djay's MIDI feedback routing, and audio channels must be checked on real Windows hardware before describing Windows as supported.

Install and run loopMIDI. Create **one port named exactly `MX2 for djay`**, then start the Windows bridge. Click **Import mapping**, confirm the import, and select that virtual device with the supplied Windows-specific mapping in djay. The bridge uses the bus's matching input/output names and filters input echoes; the Windows mapping reserves separate MIDI channels for feedback. Use the Windows mapping included with that build, not the Mac file.

Virtual MIDI feedback on Windows remains a verification point: controls responding does not prove that RGB lights or meters work. Set up the MX2's main and headphone audio devices separately in djay; Windows audio-driver behavior is also unverified. Follow the [Windows release gate](VALIDATION.md#windows-release-gate) before sharing a Windows build as supported.

## Controls and lights

Read the [complete control guide](CONTROL-GUIDE.md). Both sides control their own decks. The four pad modes are HOTCUES, STEMS, PATTERN (djay samples), and FLUX LOOP. Pads use mode colors; they do not copy the individual colors of djay hotcues.

For the mixer selector's **FX4**, disable the effect's **HOLD** option inside djay if you want momentary operation. Hold the channel's round FX ON button to apply the instant effect; release it to stop. The channel amount knob remains a filter in this adapted mode.

## If something does not work

| Symptom | Check |
|---|---|
| No controls respond | Bridge is started, the MX2 mode matches Companion, and djay uses the virtual endpoint and matching mapping |
| A button triggers twice | Disable the raw Traktor MX2 MIDI connection and stop any second bridge |
| Controls work but lights do not | Check the selected mapping; on Windows also check the separate feedback output |
| Headphones play only the live mix | Select monitor channels 3–4, turn off automatic selection, set CUE MIX toward CUE, and enable the intended deck's headphone button |
| FX4 stays on after release | Turn off the instant effect's HOLD option in djay |
| Some knobs need moving after reconnect | Move them carefully to the desired setting; the bridge has no pickup/soft-takeover function |

USB reconnect and a normal djay restart were tested successfully on the development Mac while the bridge stayed open. Recheck these behaviors on your own machine before a session. See [Validation and limitations](VALIDATION.md) for the exact scope.

## Share this integration

Share the release archive with its companion app, mappings, and these guides together. Do not share just the `.djayMidiMapping` file as a stand-alone controller solution. Keep the mapping filenames and port names intact. The package does not require the developer's personal calibration recordings or session logs.

## Testing in Parallels Desktop

Build the Windows package inside Windows, not in the Mac shared folder. Copy the source folder to your Windows desktop, install Python 3.12 (64-bit) with Tcl/Tk and the Python launcher, then run `distribution/BUILD-WINDOWS.ps1` from PowerShell. Install loopMIDI separately from its official author and create the `MX2 for djay` port. Connect the MX2 to the Windows virtual machine using Parallels USB controls; close the Mac bridge first. Test device access, PLAY/CUE, jog touch/release, lights/meters, audio main 1–2 and headphones 3–4, reconnect and app restart. Windows-on-ARM emulation and any audio drivers must be verified independently.

## Live device status and the interactive cheat sheet

The guided desktop interface starts a passive monitor when the app opens and keeps it active even if the bridge is stopped. USB presence and actual incoming reports determine the status. Native/MIDI mode is confirmed only from positive live input; if evidence becomes stale, move a control to confirm the current mode. No firmware command changes modes. Press both physical SHIFT buttons together once when instructed.

Choose Cheat sheet from the navigation or press Command-K (Mac) / Ctrl-K (Windows). Click a controller hotspot, choose a pad bank, or enable the SHIFT layer. The offline sheet also lives in the release folder under Cheat sheet/cheatsheet.html and can be opened separately at any time.

Companion supports djay Pro only. The **Stop & quit** action shows progress while stopping its bridge, then closes Companion. It does not close djay Pro.

Windows uses Microsoft Edge WebView2 Runtime for the new interface. If missing, install it from Microsoft before opening the app. Windows and Intel Mac builds remain unvalidated.

## Companion 0.5 interface

Use Connection for the three setup steps, Controls for the interactive MX2 photograph, and Audio & help for routing and troubleshooting. Live status stays at the top. If the supplied mapping is already installed, Install djay mapping does not create another copy. Select MX2 for djay inside djay and close its MIDI editor after setup.

If the crossfader follows a jog, check MIDI > Options > Crossfader Cutting Mode and disable it. Also ensure the direct Traktor MX2 MIDI connection is disabled. If the issue appears after importing a mapping, quit and reopen djay while keeping Companion running. This cleared the reported issue in the hardware retest. The captured jog MIDI contained no crossfader commands; the exact internal djay cause is not established.
