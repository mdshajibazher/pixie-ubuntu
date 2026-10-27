"""Screen RGB conversions. CMYK is an unprofiled mathematical approximation."""
import colorsys


def color_values(rgb):
    r, g, b = rgb
    red, green, blue = (v / 255 for v in rgb)
    hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
    black = 1 - max(red, green, blue)
    cmy = (0, 0, 0) if black == 1 else tuple(
        (1 - v - black) / (1 - black) for v in (red, green, blue)
    )
    return {
        'HTML': f'#{r:02X}{g:02X}{b:02X}',
        # Windows COLORREF uses 0x00BBGGRR; match original Pixie's HEX field.
        'HEX': f'0x{b:02X}{g:02X}{r:02X}',
        'RGB': f'{r}, {g}, {b}',
        'CMYK': ', '.join(str(round(v * 100)) for v in (*cmy, black)) + ' %',
        'HSV': f'{round(hue * 360) % 360}°, {round(saturation * 100)}%, {round(value * 100)}%',
    }
