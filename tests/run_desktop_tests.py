#!/usr/bin/python3
"""Run GUI tests on a temporary nested X server (requires Xephyr)."""
import os
from pathlib import Path
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[1]
display = next(f':{n}' for n in range(98, 150)
               if not Path(f'/tmp/.X11-unix/X{n}').exists() and not Path(f'/tmp/.X{n}-lock').exists())
with tempfile.TemporaryFile() as log:
    server = subprocess.Popen(['Xephyr', display, '-screen', '1024x768', '-ac', '-nolisten', 'tcp',
                               '-no-host-grab', '-title', 'Pixie verification'], stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 5
        while not Path('/tmp/.X11-unix/X' + display[1:]).exists():
            if server.poll() is not None or time.monotonic() > deadline:
                log.seek(0)
                raise RuntimeError('Cannot start Xephyr: ' + log.read().decode())
            time.sleep(.05)
        env = dict(os.environ, DISPLAY=display, PIXIE_DESKTOP_TESTS='1', GDK_BACKEND='x11', XDG_SESSION_TYPE='x11')
        # Disable host input only inside this disposable server. XTEST remains available.
        for device in ('Xephyr virtual mouse', 'Xephyr virtual keyboard'):
            subprocess.run(['xinput', 'disable', device], env=env, check=True)
        result = subprocess.run(['/usr/bin/python3', '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                env=env, cwd=root)
        raise SystemExit(result.returncode)
    finally:
        server.terminate()
        server.wait(timeout=5)
