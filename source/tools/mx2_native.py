"""Native MX2 input adapter and LED policy; no direct device operations.

Wire identities/packing are recovered; visual color policy is this bridge's design.
"""
from decode_mx2 import Decoder

PALETTE = {'red': 1, 'orange': 3, 'yellow': 5, 'green': 7, 'cyan': 9,
           'blue': 11, 'purple': 14, 'magenta': 15, 'white': 18}


class NativeInput:
    def __init__(self, profile):
        self.profile = profile['controls']
        self.decoder = Decoder(initial=True)
        self.last_analog = {}

    def reset(self):
        self.decoder = Decoder(initial=True)
        self.last_analog.clear()

    def feed(self, row):
        output = []
        for event in self.decoder.decode(row):
            if event.get('event') != 'control' or event.get('mapping_evidence') != 'static_descriptor':
                continue
            if event['initial']:
                if event['kind'] == 'analog':
                    self.last_analog[event['control']] = self.quantize(event['control'], event['raw'])
                continue  # Baseline must not start playback, load a track or jump gains.
            name = event['control']
            c = self.profile[name]
            family, ch, number = c['family'], c['channel'], c['number']
            if event['kind'] == 'button':
                output.append((0x90 | ch if event['raw'] else 0x80 | ch, [number, 127 if event['raw'] else 0]))
            elif event['kind'] == 'analog':
                value = self.quantize(name, event['raw'])
                if self.last_analog.get(name) != value:
                    self.last_analog[name] = value
                    output.append((family | ch, [number, value]))
            elif event['kind'] in ('encoder', 'jog'):
                delta = event.get('delta', 0)
                # Keep accumulated displacement, including fast moves >63ticks/frame.
                while delta:
                    step = max(-63, min(63, delta))
                    output.append((family | ch, [number, 64 + step]))
                    delta -= step
        return output

    def quantize(self, name, raw):
        c = self.profile[name]
        raw = max(0, min(4095, raw))
        # Router then normalizes the measured MIDI range; don't normalize twice.
        return round(c['min'] + raw * (c['max'] - c['min']) / 4095)


class NativeLEDs:
    def __init__(self, profile, native_map):
        self.buttons = []
        for item in native_map['buttons'].values():
            if 'ledId' in item:
                c = profile['controls'][item['name']]
                self.buttons.append((item['ledId'], c['channel'], c['number'], item['name']))
        self.meters = [0, 0]
        self.end_warning = [False, False]

    def feedback(self, status, data):
        if len(data) != 2 or status & 15 != 14:
            return
        number, value = data
        if status & 240 == 0xb0 and number in (0, 1):
            self.meters[number] = value
        if status & 240 in (0x80, 0x90) and number in (2, 3):
            self.end_warning[number - 2] = status & 240 == 0x90 and value > 0

    @staticmethod
    def color(enum, lit=True):
        return enum * 4 + (2 if lit else 0)

    @staticmethod
    def meter_count(value):
        value = max(0, min(127, value))
        return 0 if value == 0 else 1 + sum(value / 127 >= i / 9 for i in range(1, 9))

    def render(self, router, now):
        payload = [0] * 105
        for led_id, channel, number, name in self.buttons:
            lit = router.last_led.get((channel, number), 0) > 0
            if name.endswith(('.browse.favorite', '.browse.add_to_list',
                              '.browse.preview', '.browse.view')):
                lit = True
            color = PALETTE['blue']
            if name.endswith('.play'):
                color = PALETTE['green']
            elif name.endswith('.cue'):
                color = PALETTE['orange'] if channel < 2 else PALETTE['blue']
            elif '.pads.' in name:
                deck = 0 if name.startswith('left.') else 1
                pad = int(name.rsplit('.', 1)[1]) - 1
                bank = router.pad_mode[deck]
                color = (PALETTE['blue'], (PALETTE['purple'], PALETTE['cyan'], PALETTE['green'], PALETTE['red'])[pad % 4],
                         PALETTE['orange'], PALETTE['green'])[bank]
                # Preserve assignment color dimly when idle; press/state brightens it.
                payload[led_id] = self.color(color, lit)
                continue
            elif name.endswith('.stems'):
                color = PALETTE['purple']
            elif name.endswith('.pattern'):
                color = PALETTE['orange']
            elif name.endswith('.flux_loop'):
                color = PALETTE['green']
            payload[led_id] = self.color(color, True) if lit else 0
        for deck in (0, 1):
            looping = router.feedback_cache.get((deck, 32), 0) > 0
            # Design priority: active loop green; app end-warning red blinking; else blue.
            color = PALETTE['green'] if looping else PALETTE['red'] if self.end_warning[deck] else PALETTE['blue']
            visible = looping or not self.end_warning[deck] or int(now * 4) % 2 == 0
            for led_id in range(74 + deck * 6, 80 + deck * 6):
                payload[led_id] = self.color(color, True) if visible else 0
            count = self.meter_count(self.meters[deck])
            for segment in range(9):
                payload[87 + deck * 9 + segment] = 126 if segment < count else 0
        return payload
