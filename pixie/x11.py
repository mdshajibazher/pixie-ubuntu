"""Small libX11 binding: physical screen pixels and two registered shortcuts."""
import ctypes as C
from ctypes.util import find_library
from dataclasses import dataclass
import os


def channel_value(pixel, mask):
    if not mask:
        return 0
    shift = (mask & -mask).bit_length() - 1
    return round(((pixel & mask) >> shift) * 255 / (mask >> shift))


def capture_rect(x, y, width, height, size=17):
    radius = size // 2
    left, top = max(0, x - radius), max(0, y - radius)
    return left, top, min(width, x + radius + 1) - left, min(height, y + radius + 1) - top


class XImage(C.Structure):
    _fields_ = [('width', C.c_int), ('height', C.c_int), ('xoffset', C.c_int),
                ('format', C.c_int), ('data', C.c_void_p), ('byte_order', C.c_int),
                ('bitmap_unit', C.c_int), ('bitmap_bit_order', C.c_int),
                ('bitmap_pad', C.c_int), ('depth', C.c_int),
                ('bytes_per_line', C.c_int), ('bits_per_pixel', C.c_int),
                ('red_mask', C.c_ulong), ('green_mask', C.c_ulong), ('blue_mask', C.c_ulong)]


class XKeyEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('serial', C.c_ulong), ('send_event', C.c_int),
                ('display', C.c_void_p), ('window', C.c_ulong), ('root', C.c_ulong),
                ('subwindow', C.c_ulong), ('time', C.c_ulong), ('x', C.c_int),
                ('y', C.c_int), ('x_root', C.c_int), ('y_root', C.c_int),
                ('state', C.c_uint), ('keycode', C.c_uint), ('same_screen', C.c_int)]


class XEvent(C.Union):
    _fields_ = [('type', C.c_int), ('key', XKeyEvent), ('pad', C.c_long * 24)]


class XErrorEvent(C.Structure):
    _fields_ = [('type', C.c_int), ('display', C.c_void_p), ('resourceid', C.c_ulong),
                ('serial', C.c_ulong), ('error_code', C.c_ubyte),
                ('request_code', C.c_ubyte), ('minor_code', C.c_ubyte)]


@dataclass
class Sample:
    x: int
    y: int
    rgb: tuple
    width: int
    height: int
    pixels: bytes
    center_x: int
    center_y: int


class ScreenPicker:
    def __init__(self):
        if os.environ.get('XDG_SESSION_TYPE', '').lower() == 'wayland':
            raise RuntimeError('Live screen picking requires an X11 session. Log out, select your user, '
                               'choose “Ubuntu on Xorg” from the gear menu, and log back in.')
        self.lib = C.CDLL(find_library('X11') or 'libX11.so.6')
        signatures = {
            'XOpenDisplay': ([C.c_char_p], C.c_void_p),
            'XDefaultRootWindow': ([C.c_void_p], C.c_ulong),
            'XCloseDisplay': ([C.c_void_p], C.c_int),
            'XQueryPointer': ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong), C.POINTER(C.c_ulong),
                               *([C.POINTER(C.c_int)] * 4), C.POINTER(C.c_uint)], C.c_int),
            'XGetGeometry': ([C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
                             C.POINTER(C.c_int), C.POINTER(C.c_int),
                             *([C.POINTER(C.c_uint)] * 4)], C.c_int),
            'XGetImage': ([C.c_void_p, C.c_ulong, C.c_int, C.c_int, C.c_uint, C.c_uint,
                          C.c_ulong, C.c_int], C.POINTER(XImage)),
            'XGetPixel': ([C.POINTER(XImage), C.c_int, C.c_int], C.c_ulong),
            'XDestroyImage': ([C.POINTER(XImage)], C.c_int),
            'XStringToKeysym': ([C.c_char_p], C.c_ulong),
            'XKeysymToKeycode': ([C.c_void_p, C.c_ulong], C.c_ubyte),
            'XGrabKey': ([C.c_void_p, C.c_int, C.c_uint, C.c_ulong, C.c_int, C.c_int, C.c_int], C.c_int),
            'XUngrabKey': ([C.c_void_p, C.c_int, C.c_uint, C.c_ulong], C.c_int),
            'XPending': ([C.c_void_p], C.c_int),
            'XNextEvent': ([C.c_void_p, C.POINTER(XEvent)], C.c_int),
            'XSync': ([C.c_void_p, C.c_int], C.c_int),
            'XSetErrorHandler': ([C.c_void_p], C.c_void_p),
            'XkbSetDetectableAutoRepeat': ([C.c_void_p, C.c_int, C.POINTER(C.c_int)], C.c_int),
        }
        for name, (args, result) in signatures.items():
            func = getattr(self.lib, name)
            func.argtypes, func.restype = args, result
        self.display = self.lib.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('Cannot connect to the desktop. Run Pixie from your Ubuntu desktop session.')
        self.root = self.lib.XDefaultRootWindow(self.display)
        self.last_error = 0
        callback = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(XErrorEvent))
        self._error_callback = callback(self._on_error)
        self._old_handler = self.lib.XSetErrorHandler(C.cast(self._error_callback, C.c_void_p))
        self.shortcuts = {}
        self._held = set()
        supported = C.c_int()
        self.lib.XkbSetDetectableAutoRepeat(self.display, 1, C.byref(supported))

    def _on_error(self, display, event):
        if display == self.display:
            self.last_error = event.contents.error_code
        elif self._old_handler:
            handler = C.CFUNCTYPE(C.c_int, C.c_void_p, C.POINTER(XErrorEvent))(self._old_handler)
            return handler(display, event)
        return 0

    def pointer(self):
        root, child = C.c_ulong(), C.c_ulong()
        x, y, wx, wy = C.c_int(), C.c_int(), C.c_int(), C.c_int()
        mask = C.c_uint()
        if not self.lib.XQueryPointer(self.display, self.root, C.byref(root), C.byref(child),
                                     C.byref(x), C.byref(y), C.byref(wx), C.byref(wy), C.byref(mask)):
            raise RuntimeError('Pointer is on a different X screen.')
        return x.value, y.value

    def sample(self):
        x, y = self.pointer()
        root = C.c_ulong()
        gx, gy = C.c_int(), C.c_int()
        width, height, border, depth = (C.c_uint() for _ in range(4))
        if not self.lib.XGetGeometry(self.display, self.root, C.byref(root), C.byref(gx), C.byref(gy),
                                    C.byref(width), C.byref(height), C.byref(border), C.byref(depth)):
            raise RuntimeError('Cannot read screen geometry.')
        left, top, w, h = capture_rect(x, y, width.value, height.value)
        if w <= 0 or h <= 0:
            raise RuntimeError('Pointer is outside the screen.')
        image = self.lib.XGetImage(self.display, self.root, left, top, w, h, C.c_ulong(-1).value, 2)
        if not image:
            raise RuntimeError('Screen capture unavailable. Try again after the display finishes changing.')
        try:
            masks = (image.contents.red_mask, image.contents.green_mask, image.contents.blue_mask)
            pixels = bytearray()
            for row in range(h):
                for col in range(w):
                    value = self.lib.XGetPixel(image, col, row)
                    pixels.extend(channel_value(value, mask) for mask in masks)
            offset = ((y - top) * w + x - left) * 3
            return Sample(x, y, tuple(pixels[offset:offset + 3]), w, h, bytes(pixels), x - left, y - top)
        finally:
            self.lib.XDestroyImage(image)

    def register_shortcuts(self):
        unavailable = []
        for key, action in ((b'c', 'copy'), (b'f', 'freeze')):
            code = self.lib.XKeysymToKeycode(self.display, self.lib.XStringToKeysym(key))
            if not code:
                unavailable.append(action)
                continue
            self.last_error = 0
            for extra in (0, 2, 16, 18):  # Caps Lock and Num Lock
                self.lib.XGrabKey(self.display, code, 4 | 8 | extra, self.root, 0, 1, 1)
            self.lib.XSync(self.display, 0)
            if self.last_error:
                for extra in (0, 2, 16, 18):
                    self.lib.XUngrabKey(self.display, code, 4 | 8 | extra, self.root)
                unavailable.append(action)
            else:
                self.shortcuts[code] = action
        return unavailable

    def actions(self):
        result = []
        while self.lib.XPending(self.display):
            event = XEvent()
            self.lib.XNextEvent(self.display, C.byref(event))
            if event.key.keycode in self.shortcuts:
                if event.type == 2 and event.key.keycode not in self._held:
                    result.append(self.shortcuts[event.key.keycode])
                    self._held.add(event.key.keycode)
                elif event.type == 3:
                    self._held.discard(event.key.keycode)
        return result

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None
            self.lib.XSetErrorHandler(self._old_handler)
