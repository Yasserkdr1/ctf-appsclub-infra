"""Controller publishes a small, ephemeral, non-sensitive routing view."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'ansible/files/appsclub_vip_controller.py'
spec = importlib.util.spec_from_file_location('controller_public', source)
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)

class PublicationTests(unittest.TestCase):
    def test_publish_only_public_routing_data_and_withdraw(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plan = [{'team':'3','challenge':'14','node_port':30244,
                     'app_port':5000,'identity':'aaaaaaaaaaaaaaaa',
                     'vip':'10.78.3.14','source_ip':'10.79.3.1',
                     'pod_ip':'10.42.0.15','peers':['10.77.0.101/32']}]
            with patch.object(ctl,'PUBLIC_DIR',root), patch.object(ctl,'PUBLIC_MAP',root/'active-vips.json'):
                ctl.publish_routes(plan)
                data = json.loads(ctl.PUBLIC_MAP.read_text())
                self.assertEqual(data['routes']['3/14'],
                                 {'node_port':30244,'app_port':5000})
                self.assertEqual(set(data),{'version','updated_at','routes'})
                self.assertNotIn('10.42.0.15',ctl.PUBLIC_MAP.read_text())
                self.assertNotIn('10.77.0.101',ctl.PUBLIC_MAP.read_text())
                ctl.withdraw_routes()
                self.assertFalse(ctl.PUBLIC_MAP.exists())

if __name__ == '__main__': unittest.main()
