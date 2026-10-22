import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class CheatSheetTests(unittest.TestCase):
    def test_exact_physical_coverage_and_valid_positions(self):
        data = json.loads((ROOT / 'distribution/ui/controls.json').read_text())
        profile = json.loads((ROOT / 'evidence/midi-profile.json').read_text())['controls']
        controls = data['controls']
        self.assertEqual(len(controls), 116)
        self.assertEqual({row['id'] for row in controls}, set(profile))
        self.assertEqual(len({row['id'] for row in controls}), len(controls))
        for row in controls:
            self.assertTrue(row['normal'])
            self.assertGreaterEqual(row['position']['x'], 0)
            self.assertLessEqual(row['position']['x'], 1280)
            self.assertGreaterEqual(row['position']['y'], 0)
            self.assertLessEqual(row['position']['y'], 720)

    def test_reference_is_offline_and_photo_is_bundled(self):
        ui = ROOT / 'distribution/ui'
        self.assertTrue((ui / 'mx2.png').is_file())
        html = (ui / 'cheatsheet.html').read_text()
        self.assertIn('src="cheatsheet.js"', html)
        self.assertNotIn('https://fonts.', html)
        self.assertNotIn("fetch(", (ui / 'cheatsheet.js').read_text())


if __name__ == '__main__':
    unittest.main()
