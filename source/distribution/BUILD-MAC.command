#!/bin/zsh
set -e
cd -- "${0:A:h:h}"
print 'Developer build: Python 3.12 with Tk and Xcode command line tools required.'
python3 -m venv .build-venv
.build-venv/bin/python -m pip install -r distribution/requirements-build.txt
.build-venv/bin/python distribution/build_desktop.py
