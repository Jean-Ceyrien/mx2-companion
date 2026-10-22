# MX2 for djay — control guide

Choose Native with the supplied Native RGB mapping or MIDI with the original Visual Complete mapping in Companion. Left controls operate deck A; right controls operate deck B. SHIFT means **hold only the SHIFT button on that side**. Do not press both SHIFT buttons together during a session: that switches the hardware between native and MIDI mode.

These tables describe implemented assignments. They do not imply that every secondary combination has been physically tested. The mapping has 293 action rows; [Validation](VALIDATION.md) distinguishes tested behavior from remaining checks.

## Playback, jogs, and library

| Physical control | Normal action | With same-side SHIFT |
|---|---|---|
| PLAY | Play/pause | Return to start cue and pause |
| CUE | Set/return to the main cue according to playback state | Jump to beginning of track |
| SYNC | Sync tempo/beats | Toggle quantize |
| MASTER | Make this deck the tempo master | Reset tempo |
| KEY | Key lock | Match key |
| FLUX | Toggle slip | Same |
| Reverse | Censor/reverse while held | Toggle reverse |
| TT / JOG mode buttons | Select touch-scratch mode / jog mode | Same |
| Jog wheel | In TT mode, touch to scratch/hold; release resumes normal playback. Rotation without scratch touch moves/nudges the deck | Seek through the track |
| TEMPO fader | Change tempo | Same |
| BROWSE rotation | Select tracks | Select library sources |
| BROWSE press | Load selected track onto this deck | Load without instant double |
| Favorite/library queue button | Focus queue | Focus sources |
| Preparation/add-to-list button | Mark selected songs | Unmark selected songs |
| Preview button | Toggle preview | Same |
| View button | Show/hide library | Same |

## Two encoders below each jog

Rotation and pressing are separate actions. The **left encoder** is MOVE; the **right encoder** is SIZE.

| Gesture | Action |
|---|---|
| Turn left encoder | Beatjump forward/backward |
| SHIFT + turn left encoder | Move an active loop earlier/later, preserving its duration |
| Press left encoder | Loop in/out action |
| SHIFT + press left encoder | Same loop in/out action |
| Turn right encoder | Change autoloop duration |
| SHIFT + turn right encoder | Change the beatjump distance used by the left encoder |
| Press right encoder | Activate/deactivate autoloop |
| SHIFT + press right encoder | Same autoloop toggle |

## Four FX buttons and knobs at the top of each deck

Count from left to right. The first button/knob is a three-slot macro; the following three address FX1, FX2, and FX3.

| Control | Normal action | With SHIFT |
|---|---|---|
| Button 1 | Toggle each of the three FX slots | Toggle overall deck FX |
| Buttons 2, 3, 4 | Toggle FX1, FX2, FX3 respectively | Select next effect in the corresponding slot |
| Knob 1 | Set Wet/Dry for all three slots together | Same |
| Knobs 2, 3, 4 | Set FX1, FX2, FX3 parameter respectively | Same |

Button 1 inverts each slot's existing state. If some slots start on and others off, they remain different after the macro. Its light represents FX1 only, because a single button cannot display all three states.

## Pad banks

Pads are numbered across the top row **1–4**, then across the bottom row **5–8**. Each deck has its own bank selection. Press HOTCUES, STEMS, PATTERN, or FLUX LOOP to choose a bank.

| Bank | Pads 1–4 | Pads 5–8 | With SHIFT |
|---|---|---|---|
| HOTCUES | Set/jump to cues 1–4 | Set/jump to cues 5–8 | Delete the corresponding cue |
| STEMS | Toggle mute for four separated parts | Toggle solo for the same four parts | Top row toggles solo; bottom row toggles mute |
| PATTERN | Trigger sampler slots 1–4 for this deck | Trigger sampler slots 5–8 for this deck | Stop the corresponding sample |
| FLUX LOOP | Held bounce loops: 1/32, 1/16, 1/8, 1/4 beat | Held bounce loops: 1/2, 1, 2, 4 beats | Toggle persistent autoloops of the corresponding duration |

STEMS addresses djay's four-track Neural Mix channels in order **4, 3, 2, 1** from left to right. The audible parts depend on djay's selected separation layout; use its panel to identify each part. Solo is a toggle: press again to restore the other parts. The normal EQ knobs keep their EQ functions.

PATTERN is an adaptation to djay's sampler, not a recreation of Traktor's step sequencer. A sampler slot must contain a sound. Playback follows djay's sample hold setting. SHIFT + HOTCUE deletes a cue, so use a test track when learning that gesture.

## Mixer and channel FX

| Control | Action |
|---|---|
| GAIN, HIGH, MID, LOW | Own deck's gain and normal three-band EQ |
| Channel volume fader | Own channel's volume |
| Crossfader | Blend deck A/B |
| MAIN | Main output level |
| Headphone button | Toggle preview of that deck |
| CUE MIX / CUE VOL | Headphone main/preview blend and headphone level |
| Channel FX assignment buttons 1/2 | Toggle that deck's FX1/FX2 slots |
| MIC | Toggle microphone activation in djay; audio input setup is separate |

The global **FILTER / FX1 / FX2 / FX3 / FX4** selector determines what each channel's large effect knob and round FX ON button control. These round ON buttons are above the channel headphone buttons.

| Selected mode | Channel amount knob | Channel FX ON button |
|---|---|---|
| FILTER | Filter | Filter kill/active toggle |
| FX1 | FX1 Wet/Dry | Toggle FX1 |
| FX2 | FX2 Wet/Dry | Toggle FX2 |
| FX3 | FX3 Wet/Dry | Toggle FX3 |
| FX4 | Filter fallback | Instant FX4, following djay's HOLD setting |

For momentary FX4, turn **HOLD off inside djay**. Hold the round channel FX ON button to apply the effect; release it to stop. A short press then does not latch it. There is no mapped continuous instant-FX4 parameter: the amount knob deliberately retains the filter. The channel assignment buttons are a djay adaptation of Traktor's global FX-unit assignments.

## Lights

| Light | Meaning |
|---|---|
| PLAY and headphone buttons | djay's current playback/monitor selection |
| Pad-mode buttons | Selected bank on that side |
| HOTCUES pads | Blue, with state brightness; individual djay cue colors are not copied |
| STEMS pads | Four part colors, with state brightness |
| PATTERN pads | Orange, with state brightness |
| FLUX LOOP pads | Green, with state brightness |
| Channel meters | djay's deck meter feedback |
| Under-deck shell | Blue normally, green for an active loop, blinking red near track end |

Colors are choices made by this bridge. Meter segments reproduce djay's reported level; exact ballistics and clipping behavior are not claimed to match Traktor. The main clip light has no implemented clip feed. Internal native button ID 82 remains unidentified and unmapped.

### Seeing GAIN and MAIN in djay

GAIN changes the level of its own deck. djay can keep hardware gain independent of the on-screen gain knob, so a stationary on-screen knob does not by itself mean the mapping failed. Check the audible level and channel meter. Algoriddim documents this behavior: https://community.algoriddim.com/t/gain-via-midi-doesn-t-move-on-screen/34747

MAIN controls the main mix output, not a deck selected for headphone CUE preview. Open the speaker icon in djay’s top toolbar to see Main Volume. Use CUE VOL for headphone level. MAIN was physically checked from minimum to midpoint; djay’s Main Volume slider followed to about 49%.
