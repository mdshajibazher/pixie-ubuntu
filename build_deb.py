#!/usr/bin/python3
"""Build a portable Debian package without root or network access."""
from pathlib import Path
import shutil
import subprocess
import tempfile

from install import install

root = Path(__file__).resolve().parent
output = root / 'dist' / 'pixie-picker_1.0.0_all.deb'
output.parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='pixie-deb-') as temporary:
    stage = Path(temporary)
    install(stage / 'usr')
    (stage / 'usr/bin/pixie-picker').write_text('#!/bin/sh\nexec /usr/bin/python3 /usr/share/pixie-picker/launch.py "$@"\n')
    desktop = stage / 'usr/share/applications/pixie-picker.desktop'
    desktop.write_text(desktop.read_text().replace(str(stage), ''))
    control = stage / 'DEBIAN'
    control.mkdir()
    (control / 'control').write_text('Package: pixie-picker\nVersion: 1.0.0\nSection: graphics\n'
        'Priority: optional\nArchitecture: all\nMaintainer: Pixie Picker contributors\n'
        'Depends: python3 (>= 3.10), python3-gi, gir1.2-gtk-3.0, libx11-6, librsvg2-common\n'
        'Description: Native X11 screen color picker for Ubuntu\n'
        ' Live pixel sampling, magnifier, color conversions, clipboard and global shortcuts.\n')
    # The package manager updates caches via its triggers.
    cache = stage / 'usr/share/applications/mimeinfo.cache'
    cache.unlink(missing_ok=True)
    stage.chmod(0o755)
    for path in stage.rglob('*'):
        path.chmod(0o755 if path.is_dir() or path == stage / 'usr/bin/pixie-picker' else 0o644)
    subprocess.run(['desktop-file-validate', str(desktop)], check=True)
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(output)], check=True)
print(output)
