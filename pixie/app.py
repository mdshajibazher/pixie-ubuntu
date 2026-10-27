"""Compact GTK desktop interface."""
import sys
import time
from pathlib import Path

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk

from .colors import color_values
from .x11 import ScreenPicker


CSS = b'''
window.pixie { background: #181923; color: #ececf4; }
.pixie headerbar { background: #222330; color: #ececf4; border: none; }
.pixie label { color: #ececf4; }
.pixie .muted { color: #a6a8bd; font-size: 11px; }
.pixie .hero { font-family: monospace; font-size: 30px; font-weight: bold; }
.pixie .value { font-family: monospace; font-size: 12px; }
.pixie button { background: #2a2b3b; color: #ececf4; border: 1px solid #3c3e52;
                border-radius: 7px; box-shadow: none; text-shadow: none; padding: 8px 12px; }
.pixie button:hover { background: #383a50; }
.pixie button:checked { background: #514484; border-color: #9c84e8; }
.pixie button.primary { background: #aa92f4; color: #191423; font-weight: bold; border: none; }
.pixie button.primary:hover { background: #bca8ff; }
.pixie button.small { padding: 3px 7px; min-height: 20px; }
'''


class PixieWindow(Gtk.ApplicationWindow):
    def __init__(self, screen, application=None, register_shortcuts=True):
        super().__init__(application=application)
        self.screen = screen
        self.sample = None
        self.values = None
        self._message_until = 0
        self._timer = None
        self._space_down = False
        self.set_title('Pixie · Screen Color Picker')
        self.set_default_size(364, 480)
        self.set_resizable(False)
        self.set_keep_above(True)
        self.get_style_context().add_class('pixie')
        self.set_icon_name('pixie-picker')
        icon = Path(__file__).resolve().parent.parent / 'assets' / 'pixie-picker.svg'
        if icon.exists():
            self.set_icon_from_file(str(icon))
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(), provider,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._provider = provider
        header = Gtk.HeaderBar(title='Pixie', subtitle='SCREEN COLOR PICKER', show_close_button=True)
        self.set_titlebar(header)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        outer.set_border_width(20)
        self.add(outer)

        previews = Gtk.Box(spacing=12, homogeneous=True)
        self.swatch = Gtk.Image()
        self.swatch.set_size_request(148, 128)
        self.magnifier = Gtk.Image()
        self.magnifier.set_size_request(148, 128)
        previews.pack_start(self.swatch, True, True, 0)
        previews.pack_start(self.magnifier, True, True, 0)
        outer.pack_start(previews, False, False, 0)

        self.hex_label = Gtk.Label(label='—', xalign=0)
        self.hex_label.get_style_context().add_class('hero')
        outer.pack_start(self.hex_label, False, False, 0)
        self.position_label = Gtk.Label(label='Move your pointer over any color', xalign=0)
        self.position_label.get_style_context().add_class('muted')
        outer.pack_start(self.position_label, False, False, 0)

        grid = Gtk.Grid(column_spacing=10, row_spacing=7)
        self.value_labels = {}
        for row, name in enumerate(('RGB', 'HSV', 'CMYK', 'HEX')):
            label = Gtk.Label(label=name, xalign=0)
            label.get_style_context().add_class('muted')
            grid.attach(label, 0, row, 1, 1)
            value = Gtk.Label(label='—', xalign=0, hexpand=True, selectable=True)
            value.get_style_context().add_class('value')
            grid.attach(value, 1, row, 1, 1)
            self.value_labels[name] = value
            copy = Gtk.Button.new_from_icon_name('edit-copy-symbolic', Gtk.IconSize.MENU)
            copy.get_style_context().add_class('small')
            copy.set_tooltip_text(f'Copy {name}')
            copy.connect('clicked', lambda button, fmt=name: self.copy_value(fmt))
            grid.attach(copy, 2, row, 1, 1)
        self.value_labels['HEX'].set_tooltip_text('Windows COLORREF: 0xBBGGRR, as in original Pixie')
        self.value_labels['CMYK'].set_tooltip_text('Approximate CMYK; not a print color profile')
        outer.pack_start(grid, False, False, 0)

        buttons = Gtk.Box(spacing=10, homogeneous=True)
        self.freeze_button = Gtk.ToggleButton(label='Freeze')
        self.freeze_button.set_tooltip_text('Ctrl+Alt+F anywhere, or Space in this window')
        self.freeze_button.connect('toggled', self.on_freeze)
        buttons.pack_start(self.freeze_button, True, True, 0)
        self.copy_button = Gtk.Button(label='Copy #HEX')
        self.copy_button.set_sensitive(False)
        self.copy_button.get_style_context().add_class('primary')
        self.copy_button.connect('clicked', lambda button: self.copy_value('HTML'))
        buttons.pack_start(self.copy_button, True, True, 0)
        outer.pack_start(buttons, False, False, 0)

        self.status = Gtk.Label(label='● Live · point anywhere on your screen', xalign=0)
        self.status.get_style_context().add_class('muted')
        self.status.set_line_wrap(True)
        self.status.set_max_width_chars(43)
        outer.pack_start(self.status, False, False, 0)
        unavailable = screen.register_shortcuts() if register_shortcuts else []
        hint_text = 'Ctrl+Alt+C  Copy    ·    Ctrl+Alt+F  Freeze'
        if unavailable:
            hint_text = 'Shortcut unavailable: ' + ', '.join(unavailable) + '. Use the buttons.'
        hint = Gtk.Label(label=hint_text, xalign=0)
        hint.get_style_context().add_class('muted')
        hint.set_line_wrap(True)
        hint.set_max_width_chars(43)
        outer.pack_start(hint, False, False, 0)
        self.connect('key-press-event', self.on_key)
        self.connect('key-release-event', self.on_key_release)
        self.connect('focus-out-event', self.on_focus_out)
        self.connect('destroy', self.on_destroy)
        self._timer = GLib.timeout_add(50, self.tick)

    def pointer_inside(self):
        window = self.get_window()
        if not window:
            return False
        frame = window.get_frame_extents()
        scale = self.get_scale_factor()
        x, y = self.screen.pointer()
        return (frame.x * scale <= x < (frame.x + frame.width) * scale and
                frame.y * scale <= y < (frame.y + frame.height) * scale)

    def update_sample(self):
        if self.freeze_button.get_active() or self.pointer_inside():
            return
        self.sample = self.screen.sample()
        self.values = color_values(self.sample.rgb)
        self.hex_label.set_text(self.values['HTML'])
        self.position_label.set_text(f'PIXEL  {self.sample.x}, {self.sample.y}   ·   8× magnifier')
        for name, label in self.value_labels.items():
            label.set_text(self.values[name])
        self.copy_button.set_sensitive(True)
        self.render_previews()

    def tick(self):
        try:
            self.update_sample()
            for action in self.screen.actions():
                if action == 'copy':
                    self.copy_value('HTML')
                elif action == 'freeze':
                    self.freeze_button.set_active(not self.freeze_button.get_active())
            if time.monotonic() >= self._message_until:
                self.status.set_text('Ⅱ Frozen · resume to pick another color' if self.freeze_button.get_active()
                                     else '● Live · point anywhere on your screen')
        except RuntimeError as error:
            self.message(str(error))
        return True

    def message(self, text):
        self.status.set_text(text)
        self._message_until = time.monotonic() + 2

    def on_freeze(self, button):
        button.set_label('Resume' if button.get_active() else 'Freeze')
        self._message_until = 0

    def copy_value(self, name):
        if self.values is None:
            self.message('Point to a color first.')
            return
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(self.values[name], -1)
        clipboard.store()
        self.message(f'Copied {self.values[name]}')

    def on_key(self, widget, event):
        if event.keyval == Gdk.KEY_space:
            if not self._space_down:
                self._space_down = True
                self.freeze_button.set_active(not self.freeze_button.get_active())
            return True
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.copy_value('HTML')
            return True
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False

    def on_key_release(self, widget, event):
        if event.keyval == Gdk.KEY_space:
            self._space_down = False
            return True
        return False

    def on_focus_out(self, widget, event):
        self._space_down = False
        return False

    def render_previews(self):
        sample = self.sample
        swatch = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 148, 128)
        r, g, b = sample.rgb
        swatch.fill((r << 24) | (g << 16) | (b << 8) | 255)
        self.swatch.set_from_pixbuf(swatch)
        source = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(sample.pixels),
                    GdkPixbuf.Colorspace.RGB, False, 8, sample.width, sample.height, sample.width * 3)
        scaled = source.scale_simple(sample.width * 8, sample.height * 8, GdkPixbuf.InterpType.NEAREST)
        canvas = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 148, 128)
        canvas.fill(0x191B26FF)
        ox, oy = 74 - (sample.center_x * 8 + 4), 64 - (sample.center_y * 8 + 4)
        sx, sy = max(0, -ox), max(0, -oy)
        dx, dy = max(0, ox), max(0, oy)
        width = min(scaled.get_width() - sx, 148 - dx)
        height = min(scaled.get_height() - sy, 128 - dy)
        scaled.copy_area(sx, sy, width, height, canvas, dx, dy)
        for size, color in ((12, 0x000000FF), (10, 0xFFFFFFFF), (8, (r << 24) | (g << 16) | (b << 8) | 255)):
            box = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, size, size)
            box.fill(color)
            box.copy_area(0, 0, size, size, canvas, 74 - size // 2, 64 - size // 2)
        self.magnifier.set_from_pixbuf(canvas)

    def on_destroy(self, widget):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None
        Gtk.StyleContext.remove_provider_for_screen(self.get_screen(), self._provider)


class PixieApplication(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='io.github.pixiepicker.Desktop', flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.screen = None
        self.window = None

    def do_activate(self):
        if self.window:
            self.window.present()
            return
        try:
            self.screen = ScreenPicker()
        except (RuntimeError, OSError) as error:
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE,
                                       text='Pixie cannot start screen capture')
            dialog.format_secondary_text(str(error))
            dialog.run()
            dialog.destroy()
            self.quit()
            return
        self.window = PixieWindow(self.screen, self)
        self.window.show_all()

    def do_shutdown(self):
        if self.screen:
            self.screen.close()
        Gtk.Application.do_shutdown(self)


def main():
    GLib.set_prgname('pixie-picker')
    GLib.set_application_name('Pixie Color Picker')
    if not Gtk.init_check()[0]:
        print('Pixie needs an Ubuntu desktop display. Run it from your desktop session.', file=sys.stderr)
        return 1
    return PixieApplication().run(sys.argv)
