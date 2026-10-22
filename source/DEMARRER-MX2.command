#!/bin/zsh
cd -- "${0:A:h}"
print 'MX2 → djay : gardez cette fenêtre ouverte pendant votre session.'
print 'Le MX2 doit être connecté et en mode MIDI.'
print 'Dans djay : MX2 for djay actif, Traktor MX2 direct désactivé.'
exec /usr/bin/python3 tools/mx2_bridge.py
