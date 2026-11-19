"""Fail-closed display contract for team-scoped VIPs."""
import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'ansible/files/ctfd/plugins/ctfd_chall_manager/utils/appsclub_connection_info.py'
spec = importlib.util.spec_from_file_location('appsclub_connection_info', PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class VIPDisplayTests(unittest.TestCase):
    def test_two_challenges_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = Path(temp) / 'active-vips.json'
            def store(ts, routes):
                manifest.write_text(json.dumps({'version':1, 'updated_at':ts, 'routes':routes}))
            routes = {'2/13': {'node_port':30885, 'app_port':8000},
                      '3/14': {'node_port':30244, 'app_port':5000}}
            with patch.object(module, 'ACTIVE_MAP', manifest):
                store(int(time.time()), routes)
                self.assertEqual(module.player_vip(13, 2, 'http://10.60.2.10:30885'),
                                 'http://10.78.2.13:8000')
                self.assertEqual(module.player_vip(14, 3, 'http://10.60.2.10:30244'),
                                 'http://10.78.3.14:5000')
                self.assertEqual(module.player_vip(14, 2, 'http://10.60.2.10:30244'),
                                 module.UNAVAILABLE)
                self.assertEqual(module.player_vip(14, 3, 'http://10.60.2.10:39999'),
                                 module.UNAVAILABLE)
                self.assertEqual(module.player_vip(14, 3, 'http://evil:30244'),
                                 module.UNAVAILABLE)
                self.assertEqual(module.player_vip(14, 3, 'hidden'), 'hidden')
                store(int(time.time()) - 90, routes)
                self.assertEqual(module.player_vip(13, 2, 'http://10.60.2.10:30885'),
                                 module.UNAVAILABLE)
                manifest.unlink()
                self.assertEqual(module.player_vip(13, 2, 'http://10.60.2.10:30885'),
                                 module.UNAVAILABLE)

if __name__ == '__main__': unittest.main()
