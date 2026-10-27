#!/usr/bin/python3
"""Install for the current user, or into --prefix for packaging/testing."""
import argparse
from pathlib import Path
import shlex
import shutil
import subprocess


def install(prefix):
    source = Path(__file__).resolve().parent
    target = prefix / 'share' / 'pixie-picker'
    target.mkdir(parents=True, exist_ok=True)
    for directory in ('pixie', 'assets'):
        shutil.copytree(source / directory, target / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for filename in ('launch.py', 'README.md'):
        shutil.copy2(source / filename, target / filename)
    binary = prefix / 'bin' / 'pixie-picker'
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text('#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(target / 'launch.py')) + ' "$@"\n')
    binary.chmod(0o755)
    icon = prefix / 'share/icons/hicolor/scalable/apps/pixie-picker.svg'
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'assets/pixie-picker.svg', icon)
    desktop = prefix / 'share/applications/pixie-picker.desktop'
    desktop.parent.mkdir(parents=True, exist_ok=True)
    # Desktop Exec uses its own escaping, not shell quoting.
    executable = str(binary).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
    desktop.write_text('[Desktop Entry]\nType=Application\nName=Pixie Color Picker\n'
                       'Comment=Pick colors anywhere on your X11 desktop\n'
                       f'Exec="{executable}"\nIcon=pixie-picker\nTerminal=false\n'
                       'Categories=Graphics;\nKeywords=color;picker;eyedropper;hex;rgb;\n'
                       'StartupNotify=true\nStartupWMClass=pixie-picker\n')
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(desktop.parent)], check=True)
    print(f'Installed Pixie Color Picker: {binary}\nOpen it from the Ubuntu applications menu.')
    return binary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prefix', type=Path, default=Path.home() / '.local')
    options = parser.parse_args()
    install(options.prefix.expanduser().resolve())
