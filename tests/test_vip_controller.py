import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]

def load(name, filepath):
    spec = importlib.util.spec_from_file_location(name, filepath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

ctl = load('controller', ROOT / 'ansible/files/appsclub_vip_controller.py')
helper = load('worker_helper', ROOT / 'ansible/files/appsclub_vip_k8s.py')
cleanup = load('legacy_cleanup', ROOT / 'ansible/files/appsclub_vip_cleanup_legacy.py')

class ControllerTests(unittest.TestCase):
    def test_firewall_no_unrestricted_established(self):
        p = [{'team':'2','challenge':'13','identity':'356e098052efd16a',
              'vip':'10.78.2.13','source_ip':'10.79.2.1','pod_ip':'10.42.0.14',
              'peers':['10.77.0.10/32'], 'app_port':8000, 'node_port':30885}]
        rules=ctl.build_rules(p)
        self.assertEqual(len(rules),4)
        fwds=[args for table,chain,args in rules if chain=='ACVIP_FWD']
        self.assertEqual(len(fwds),2)
        self.assertTrue(all('-s' in r and '-d' in r for r in fwds))
        self.assertTrue(any('ESTABLISHED,RELATED' in r for r in fwds))
        self.assertTrue(any('10.77.0.10/32' in r and '10.42.0.14/32' in r for r in fwds))
        self.assertEqual(ctl.build_rules([]), [])

    def test_policy_wrapper_rejects_privilege_escalation(self):
        x={'team':'2','challenge':'13','identity':'356e098052efd16a',
           'vip':'10.78.2.13','source_ip':'10.79.2.1','pod_ip':'10.42.0.14',
           'peers':['10.77.0.10/32'], 'app_port':8000, 'node_port':30885}
        p=ctl.policy(x)
        self.assertEqual(helper.validate_policy(p),p)
        p['spec']['ingress'][0]['ports'].append({'protocol':'UDP'})
        with self.assertRaises(ValueError): helper.validate_policy(p)
        p = ctl.policy(x)
        p['spec']['ingress'][0]['ports'] = [{'protocol':'TCP','port':"5000"}]
        with self.assertRaises(ValueError): helper.validate_policy(p)

    def test_legacy_cleaner_is_specific(self):
        rule = ['-A','FORWARD','-s','10.77.0.10/32','-d','10.60.2.10/32',
                '-i','wg0','-p','tcp','-m','tcp','--dport','32667','-j','ACCEPT']
        self.assertTrue(cleanup.is_fixed(rule, 'FORWARD', 'filter'))
        rule[rule.index('-d')+1] = '10.60.2.11/32'
        self.assertFalse(cleanup.is_fixed(rule, 'FORWARD', 'filter'))
        returns = ['-A','FORWARD','-i','eth0','-o','wg0','-m','conntrack',
                   '--ctstate','ESTABLISHED,RELATED','-j','ACCEPT']
        self.assertTrue(cleanup.is_fixed(returns, 'FORWARD', 'filter'))

    def test_ownership_selects_one_ready_pod(self):
        ident='356e098052efd16a'
        svc={'kind':'Service','metadata':{'labels':{ctl.POD_LABEL:ident}},
             'spec':{'ports':[{'nodePort':30885, 'port':8000, 'targetPort':8000}]}}
        pod={'kind':'Pod','metadata':{'labels':{ctl.POD_LABEL:ident}},
             'status':{'podIP':'10.42.0.14','phase':'Running',
                       'conditions':[{'type':'Ready','status':'True'}]}}
        np={'kind':'NetworkPolicy','metadata':{'name':'emp-ntp-test','labels':{ctl.POD_LABEL:ident}}}
        with patch.object(ctl,'get_instances',return_value=[{'challengeId':'13','sourceId':'2',
                                                            'connectionInfo':'http://10.60.2.10:30885'}]):
            result=ctl.desired({'2':['10.77.0.10/32']},[svc,pod,np])
        self.assertEqual(result[0]['vip'],'10.78.2.13')
        self.assertEqual(result[0]['pod_ip'],'10.42.0.14')
        self.assertEqual(result[0]['app_port'],8000)
        self.assertEqual(result[0]['node_port'],30885)

    def test_dynamic_port_isolation(self):
        p = [{'team':'3','challenge':'14','identity':'356e098052efd16a',
              'vip':'10.78.3.14','source_ip':'10.79.3.1','pod_ip':'10.42.0.15',
              'peers':['10.77.0.101/32'], 'app_port':5000, 'node_port':30244}]
        rules = ctl.build_rules(p)
        self.assertEqual(len(rules), 4)
        self.assertTrue(all('--dport' in args for table,chain,args in rules
                            if chain != 'ACVIP_FWD' or 'ESTABLISHED,RELATED' not in args))
        self.assertTrue(all('5000' in args for _,_,args in rules))
        self.assertEqual(ctl.policy(p[0])['spec']['ingress'][0]['ports'],
                         [{'protocol':'TCP','port':5000}])
        self.assertEqual(helper.validate_policy(ctl.policy(p[0])),ctl.policy(p[0]))

if __name__=='__main__': unittest.main()
