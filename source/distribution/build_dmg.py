#!/usr/bin/env python3
"""Create the macOS drag-to-Applications disk image from the verified ZIP."""
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
VERSION = '0.5.0'
ARCHIVE = ROOT / 'release' / f'MX2-Companion-{VERSION}-macOS-arm64.zip'
OUTPUT = ROOT / 'release' / f'MX2-Companion-{VERSION}-macOS-arm64.dmg'
VOLUME = f'MX2 Companion {VERSION}'


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def background(path):
    scale = 1
    canvas = Image.new('RGB', (720 * scale, 460 * scale), '#f2f3f6')
    draw = ImageDraw.Draw(canvas)
    font = ROOT / 'distribution/ui/fonts/SpaceGrotesk-Variable.ttf'
    body = ROOT / 'distribution/ui/fonts/Manrope-Variable.ttf'
    title = ImageFont.truetype(str(font), 34 * scale)
    label = ImageFont.truetype(str(body), 15 * scale)
    small = ImageFont.truetype(str(body), 12 * scale)
    draw.rectangle((0, 0, 720 * scale, 8 * scale), fill='#101928')
    draw.text((38 * scale, 38 * scale), 'Install MX2 Companion', font=title, fill='#101928')
    draw.text((40 * scale, 91 * scale), 'Drag the app into Applications.', font=label, fill='#4e5766')
    # Finder draws the two real icons on top of these quiet landing areas.
    draw.rounded_rectangle((57 * scale, 150 * scale, 285 * scale, 365 * scale),
                           radius=17 * scale, fill='#e5e9f1')
    draw.rounded_rectangle((435 * scale, 150 * scale, 663 * scale, 365 * scale),
                           radius=17 * scale, fill='#e5e9f1')
    draw.line((321 * scale, 250 * scale, 399 * scale, 250 * scale),
              fill='#0000dd', width=5 * scale)
    draw.polygon([(399 * scale, 250 * scale), (381 * scale, 238 * scale),
                  (381 * scale, 262 * scale)], fill='#0000dd')
    draw.text((39 * scale, 404 * scale), 'MX2 for djay Pro', font=label, fill='#101928')
    draw.text((39 * scale, 429 * scale), 'macOS · Apple silicon', font=small, fill='#677080')
    canvas.save(path)


def layout(mount):
    image = mount / '.background/installer.png'
    script = '''tell application "Finder"
    tell disk "''' + VOLUME + '''"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {140, 140, 860, 600}
        set opts to icon view options of container window
        set arrangement of opts to not arranged
        set icon size of opts to 112
        set text size of opts to 14
        set background picture of opts to (POSIX file "''' + str(image) + '''" as alias)
        set position of item "MX2 Companion.app" of container window to {170, 260}
        set position of item "Applications" of container window to {550, 260}
        update without registering applications
        close
    end tell
end tell'''
    run('/usr/bin/osascript', '-e', script)


def main():
    if not ARCHIVE.is_file():
        raise SystemExit(f'Missing release archive: {ARCHIVE}')
    with tempfile.TemporaryDirectory(prefix='mx2-dmg-') as temporary:
        temp = Path(temporary)
        extracted = temp / 'extracted'
        extracted.mkdir()
        run('/usr/bin/ditto', '-x', '-k', ARCHIVE, extracted)
        app = extracted / f'MX2-Companion-{VERSION}-macOS-arm64/MX2 Companion.app'
        run('/usr/bin/codesign', '--verify', '--deep', '--strict', app)
        writable = temp / 'working.dmg'
        run('/usr/bin/hdiutil', 'create', '-size', '120m', '-fs', 'HFS+',
            '-volname', VOLUME, '-ov', writable)
        attached = subprocess.run(['/usr/bin/hdiutil', 'attach', '-readwrite', '-noverify',
                                   '-noautoopen', '-plist', str(writable)],
                                  check=True, capture_output=True)
        devices = plistlib.loads(attached.stdout)['system-entities']
        mount = Path(next(row['mount-point'] for row in devices if 'mount-point' in row))
        try:
            run('/usr/bin/ditto', '--norsrc', '--noextattr', app, mount / app.name)
            for name in ['LICENSE', 'LICENSING.md']:
                shutil.copy2(ROOT / name, mount / name)
            (mount / 'Applications').symlink_to('/Applications')
            image = mount / '.background/installer.png'
            image.parent.mkdir()
            background(image)
            layout(mount)
        finally:
            run('/usr/bin/hdiutil', 'detach', mount)
        if OUTPUT.exists():
            OUTPUT.unlink()
        run('/usr/bin/hdiutil', 'convert', writable, '-format', 'UDZO',
            '-imagekey', 'zlib-level=9', '-o', OUTPUT)
        run('/usr/bin/hdiutil', 'verify', OUTPUT)
    print(OUTPUT)


if __name__ == '__main__':
    main()
