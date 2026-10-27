"""Opt-in integration tests: briefly open windows and restore pointer position."""
import ctypes as C
from ctypes.util import find_library
import os
import time
import unittest


@unittest.skipUnless(os.environ.get('PIXIE_DESKTOP_TESTS') == '1', 'requires an X11 desktop')
class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gtk, Gdk
        from pixie.app import PixieWindow
        from pixie.x11 import ScreenPicker
        cls.Gtk, cls.Gdk, cls.Window = Gtk, Gdk, PixieWindow
        cls.screen = ScreenPicker()
        cls.original_pointer = cls.screen.pointer()
        lib = cls.screen.lib
        lib.XCreateSimpleWindow.argtypes = [C.c_void_p, C.c_ulong, C.c_int, C.c_int,
                                           C.c_uint, C.c_uint, C.c_uint, C.c_ulong, C.c_ulong]
        lib.XCreateSimpleWindow.restype = C.c_ulong
        lib.XMapRaised.argtypes = [C.c_void_p, C.c_ulong]
        lib.XTranslateCoordinates.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_int, C.c_int,
                                             C.POINTER(C.c_int), C.POINTER(C.c_int), C.POINTER(C.c_ulong)]
        lib.XDestroyWindow.argtypes = [C.c_void_p, C.c_ulong]
        lib.XWarpPointer.argtypes = [C.c_void_p, C.c_ulong, C.c_ulong, C.c_int,
                                    C.c_int, C.c_uint, C.c_uint, C.c_int, C.c_int]
        cls.target = lib.XCreateSimpleWindow(cls.screen.display, cls.screen.root,
                                            30, 30, 160, 160, 0, 0, 0xF0AD00)
        lib.XMapRaised(cls.screen.display, cls.target)
        lib.XSync(cls.screen.display, 0)

    @classmethod
    def tearDownClass(cls):
        cls.warp(*cls.original_pointer)
        cls.screen.lib.XDestroyWindow(cls.screen.display, cls.target)
        cls.screen.close()

    @classmethod
    def warp(cls, x, y):
        cls.screen.lib.XWarpPointer(cls.screen.display, 0, cls.screen.root, 0, 0, 0, 0, x, y)
        cls.screen.lib.XSync(cls.screen.display, 0)

    def drain(self):
        deadline = time.monotonic() + 0.3
        while time.monotonic() < deadline:
            while self.Gtk.events_pending():
                self.Gtk.main_iteration_do(False)
            time.sleep(0.01)

    def target_point(self):
        self.drain()
        x, y, child = C.c_int(), C.c_int(), C.c_ulong()
        self.screen.lib.XTranslateCoordinates(self.screen.display, self.target, self.screen.root,
                                              80, 80, C.byref(x), C.byref(y), C.byref(child))
        return x.value, y.value

    def test_live_capture_and_edges(self):
        point = self.target_point()
        self.warp(*point)
        self.drain()
        sample = self.screen.sample()
        self.assertEqual(sample.rgb, (240, 173, 0))
        self.assertEqual((sample.x, sample.y), point)
        self.assertEqual(len(sample.pixels), sample.width * sample.height * 3)
        self.warp(0, 0)
        sample = self.screen.sample()
        self.assertEqual((sample.width, sample.height), (9, 9))
        self.assertEqual((sample.center_x, sample.center_y), (0, 0))

    def test_global_shortcuts_and_conflicts(self):
        from pixie.x11 import ScreenPicker
        self.assertEqual(self.screen.register_shortcuts(), [])
        other = ScreenPicker()
        try:
            self.assertEqual(other.register_shortcuts(), ['copy', 'freeze'])
        finally:
            other.close()
        xtest = C.CDLL(find_library('Xtst'))
        xtest.XTestFakeKeyEvent.argtypes = [C.c_void_p, C.c_uint, C.c_int, C.c_ulong]
        for key, expected in ((b'c', 'copy'), (b'f', 'freeze')):
            codes = [self.screen.lib.XKeysymToKeycode(self.screen.display,
                        self.screen.lib.XStringToKeysym(name)) for name in (b'Control_L', b'Alt_L', key)]
            for code in codes:
                xtest.XTestFakeKeyEvent(self.screen.display, code, 1, 0)
            self.screen.lib.XSync(self.screen.display, 0)
            time.sleep(1.0)  # Holding a shortcut past autorepeat must fire only once.
            for code in reversed(codes):
                xtest.XTestFakeKeyEvent(self.screen.display, code, 0, 0)
            self.screen.lib.XSync(self.screen.display, 0)
            self.assertEqual(self.screen.actions(), [expected])

    def test_window_freeze_and_clipboard(self):
        window = self.Window(self.screen, register_shortcuts=False)
        window.move(400, 200)
        window.show_all()
        try:
            self.warp(*self.target_point())
            self.drain()
            window.update_sample()
            self.assertEqual(window.values['HTML'], '#F0AD00')
            event = self.Gdk.Event.new(self.Gdk.EventType.KEY_PRESS)
            event.keyval = self.Gdk.KEY_space
            window.on_key(window, event)
            window.on_key(window, event)
            self.assertTrue(window.freeze_button.get_active())
            window.on_key_release(window, event)
            window.on_key(window, event)
            self.assertFalse(window.freeze_button.get_active())
            window.on_key_release(window, event)
            self.assertIsNotNone(window.swatch.get_pixbuf())
            self.assertIsNotNone(window.magnifier.get_pixbuf())
            window.freeze_button.set_active(True)
            self.warp(0, 0)
            self.drain()
            self.assertEqual(window.values['HTML'], '#F0AD00')
            window.copy_value('HTML')
            clipboard = self.Gtk.Clipboard.get(self.Gdk.SELECTION_CLIPBOARD)
            self.assertEqual(clipboard.wait_for_text(), '#F0AD00')
            if os.environ.get('PIXIE_SCREENSHOT'):
                width, height = window.get_window().get_width(), window.get_window().get_height()
                preview = self.Gdk.pixbuf_get_from_window(window.get_window(), 0, 0, width, height)
                preview.savev(os.environ['PIXIE_SCREENSHOT'], 'png', [], [])
            window.freeze_button.set_active(False)
            self.warp(*self.target_point())
            self.drain()
            self.assertEqual(window.values['RGB'], '240, 173, 0')
            # Entering the picker must not overwrite the last external color.
            wx, wy = window.get_position()
            self.warp(wx + 60, wy + 80)
            self.drain()
            self.assertEqual(window.values['HTML'], '#F0AD00')
        finally:
            window.destroy()


if __name__ == '__main__':
    unittest.main()
