# Third-party components

The packaged application includes CPython (Python Software Foundation License), pywebview (BSD-3-Clause), PyObjC on macOS, and a PyInstaller bootloader (GPL with its distribution exception). Windows builds also include HIDAPI/cython-hidapi, Mido and python-rtmidi. Build scripts collect distribution license metadata into the package where supplied. loopMIDI is separately installed from its author and is not redistributed here.

- Python: https://docs.python.org/3/license.html
- Tcl/Tk: https://www.tcl-lang.org/software/tcltk/license.html
- PyInstaller exception: https://pyinstaller.org/en/stable/license.html
- HIDAPI binding: https://github.com/trezor/cython-hidapi
- Mido: https://github.com/mido/mido
- python-rtmidi: https://github.com/SpotlightKid/python-rtmidi
- loopMIDI: https://www.tobias-erichsen.de/software/loopmidi.html
- Manrope: https://github.com/google/fonts/tree/main/ofl/manrope (SIL Open Font License 1.1)
- Space Grotesk: https://github.com/google/fonts/tree/main/ofl/spacegrotesk (SIL Open Font License 1.1)

The font license texts are bundled in `distribution/ui/fonts/` for offline builds.

Native Instruments, Traktor and Algoriddim/djay names identify compatible products. No Traktor/djay binaries, music, personal calibration logs or account files are redistributed.

Controller photograph: Native Instruments, from https://www.native-instruments.com/products/traktor-mx2 ; the photo is a product reference and is not covered by the project’s code license.
