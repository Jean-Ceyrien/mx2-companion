"""Disjoint Windows loopback input/feedback addresses; no timing-based echo filter."""


def encode_feedback(status, data):
    family, channel = status & 240, status & 15
    number, value = data
    if family == 176 and channel == 14 and number in (0, 1):
        return status, list(data)
    if family not in (128, 144):
        raise ValueError('Unsupported feedback family')
    if channel in (0, 1):
        return family | (10 + channel), list(data)
    if channel in (4, 5):
        return family | (channel + 8), list(data)
    if channel in (6, 7) and 0 <= number < 56:
        return family | 14, [number + 64 * (channel - 6), value]
    if channel == 14 and number in (2, 3):
        return family | 12, [120 + number - 2, value]
    if channel == 15 and number == 5:
        return family | 13, [120, value]
    raise ValueError('Unspecified feedback address')


def decode_feedback(status, data):
    family, channel = status & 240, status & 15
    if len(data) != 2:
        return None
    number, value = data
    if family == 176:
        return (status, list(data)) if channel == 14 and number in (0, 1) else None
    if family not in (128, 144):
        return None
    if channel in (10, 11):
        return family | (channel - 10), list(data)
    if channel == 12 and number in (120, 121):
        return family | 14, [number - 118, value]
    if channel == 13 and number == 120:
        return family | 15, [5, value]
    if channel in (12, 13):
        return family | (channel - 8), list(data)
    if channel == 14 and (number < 56 or 64 <= number < 120):
        return family | (6 + number // 64), [number % 64, value]
    return None
