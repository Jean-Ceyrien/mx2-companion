from copy import deepcopy
import unittest
from build_djay_native_mapping import build as native_build
from build_djay_windows_mapping import build
from mx2_windows_feedback import encode_feedback, decode_feedback


class WindowsMappingTests(unittest.TestCase):
    def test_all_actions_preserved_feedback_disjoint_and_roundtrips(self):
        native, windows = native_build(), build()
        inputs = set()
        for original, changed in zip(native['controls'], windows['controls']):
            expected, actual = deepcopy(original), deepcopy(changed)
            expected.pop('output', None); actual.pop('output', None)
            self.assertEqual(expected, actual)
            self.assertNotIn(changed['midiChannel'], range(10, 15))
            inputs.add((changed['midiMessageType'], changed['midiChannel'], changed['midiData']))
            if 'output' in original and original['midiChannel'] in (2, 3, 8, 9):
                self.assertNotIn('output', changed)
            elif 'output' in original:
                out = changed['output']
                self.assertIn(out['midiChannel'], range(10, 15))
                self.assertNotIn((out['midiMessageType'], out['midiChannel'], out['midiData']), inputs)
                status = (176 if out['midiMessageType'] == 3 else 144) | out['midiChannel']
                decoded = decode_feedback(status, [out['midiData'], 127])
                self.assertEqual(decoded, ((176 if original['midiMessageType'] == 3 else 144) | original['midiChannel'], [original['midiData'], 127]))
        for original, changed in zip(native['outputs'], windows['outputs']):
            status = (176 if original['midiMessageType'] == 3 else 144) | original['midiChannel']
            encoded, data = encode_feedback(status, [original['midiData'], 127])
            self.assertEqual(decode_feedback(encoded, data), (status, [original['midiData'], 127]))

    def test_unknown_feedback_and_control_echoes_ignored(self):
        for ch in list(range(10)) + [15]:
            self.assertIsNone(decode_feedback(144 | ch, [29, 127]))
        self.assertIsNone(decode_feedback(176 | 10, [0, 127]))
        self.assertIsNone(decode_feedback(144 | 14, [63, 127]))


if __name__ == '__main__':
    unittest.main()
