# Pixie for Ubuntu

Build a small native screen color picker inspired by Nattyware Pixie. The user's
Ubuntu 24.04 session is X11 and already has Python 3, GTK 3, GdkPixbuf and libX11.

Use an always-on-top GTK window showing a swatch, pixel magnifier, coordinates,
HTML/HEX, RGB, CMYK and HSV. Sample live at 20 Hz; keep the last external color
while the pointer is over the window. Support freezing and copying with buttons
and global Ctrl+Alt+F / Ctrl+Alt+C shortcuts. Explain shortcut conflicts.

Approaches considered: GTK/Python (selected by agent: native, existing dependencies),
Qt (extra dependencies), running the Windows executable through Wine (does not
meet the request for an Ubuntu application). No use of the executable's code/assets.

X11 reads physical pixels and screen coordinates directly. Wayland launches show
an explicit unsupported-session message rather than incorrect XWayland colors.
No screen recordings, network access, telemetry or background services.

Deliver source, a local launcher, a user installation script and a .deb package.
Validate color conversions, edge capture, live screen reads, freeze, clipboard,
shortcuts and the install layout. CMYK is a mathematical approximation, not an ICC
print conversion. User has authorized building; implementation details are agent choices.
