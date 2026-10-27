import subprocess
import unittest


class LaunchTests(unittest.TestCase):
    def test_fresh_process_loads_gtk3(self):
        result = subprocess.run(['/usr/bin/python3', '-c',
                                 'import pixie.app; assert pixie.app.Gdk._version == "3.0"'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
