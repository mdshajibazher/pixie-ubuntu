import unittest

from pixie.colors import color_values
from pixie.x11 import capture_rect, channel_value


class ColorTests(unittest.TestCase):
    def test_red_formats(self):
        values = color_values((255, 0, 0))
        self.assertEqual(values['HTML'], '#FF0000')
        self.assertEqual(values['RGB'], '255, 0, 0')
        self.assertEqual(values['CMYK'], '0, 100, 100, 0 %')
        self.assertEqual(values['HSV'], '0°, 100%, 100%')

    def test_black_and_white(self):
        self.assertEqual(color_values((0, 0, 0))['CMYK'], '0, 0, 0, 100 %')
        self.assertEqual(color_values((255, 255, 255))['CMYK'], '0, 0, 0, 0 %')
        self.assertEqual(color_values((128, 128, 128))['HSV'], '0°, 0%, 50%')

    def test_mixed_color_and_windows_hex(self):
        values = color_values((240, 173, 0))
        self.assertEqual(values['HTML'], '#F0AD00')
        self.assertEqual(values['HEX'], '0x00ADF0')
        self.assertEqual(values['HSV'], '43°, 100%, 94%')
        self.assertEqual(values['CMYK'], '0, 28, 100, 6 %')

    def test_pixel_masks(self):
        self.assertEqual(channel_value(0xAB3412, 0xFF0000), 171)
        self.assertEqual(channel_value(0xAB3412, 0x00FF00), 52)
        self.assertEqual(channel_value(0xF800, 0xF800), 255)
        self.assertEqual(channel_value(0, 0), 0)

    def test_capture_edges(self):
        self.assertEqual(capture_rect(50, 50, 100, 100, 17), (42, 42, 17, 17))
        self.assertEqual(capture_rect(0, 0, 100, 100, 17), (0, 0, 9, 9))
        self.assertEqual(capture_rect(99, 99, 100, 100, 17), (91, 91, 9, 9))
        self.assertEqual(capture_rect(1, 1, 3, 3, 17), (0, 0, 3, 3))


if __name__ == '__main__':
    unittest.main()
