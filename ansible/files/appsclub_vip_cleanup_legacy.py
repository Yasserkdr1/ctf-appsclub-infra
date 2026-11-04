#!/usr/bin/python3
"""Remove ONLY obsolete pilot WireGuard forwarding/NAT rules on gateway.

Use after changing the persistent wg0.conf.j2 template. Does not touch ACVIP,
Docker, Kubernetes, default DROP, or unrelated forwarding rules.
"""
import ipaddress
import shlex
import subprocess

IPT = '/usr/sbin/iptables'
ALLOWED_OLD = {'CTF_VIP_FWD', 'CTF_VIP_DNAT', 'CTF_VIP_SNAT',
               'AC_VIP_FORWARD', 'AC_VIP_DNAT', 'AC_VIP_SNAT'}


def cmd(*args, table='filter', check=True):
    argv = [IPT, '-w'] + (['-t', table] if table != 'filter' else []) + list(args)
    p = subprocess.run(argv, capture_output=True, text=True)
    if check and p.returncode:
        raise RuntimeError('iptables command failed: ' + p.stderr.strip())
    return p


def rules(chain, table='filter'):
    return [shlex.split(line) for line in cmd('-S', chain, table=table).stdout.splitlines()
            if line.startswith('-A ' + chain + ' ')]


def val(rule, flag):
    try:
        return rule[rule.index(flag) + 1]
    except (ValueError, IndexError):
        return ''


def net_eq(s, network):
    try:
        return ipaddress.ip_network(s, strict=False) == ipaddress.ip_network(network)
    except ValueError:
        return False


def is_fixed(rule, chain, table):
    if val(rule, '-j') == 'ACCEPT' and table == 'filter' and chain == 'FORWARD':
        pilot_forward = (val(rule, '-i') == 'wg0' and val(rule, '-p') == 'tcp'
                         and net_eq(val(rule, '-s'), '10.77.0.10/32')
                         and net_eq(val(rule, '-d'), '10.60.2.10/32')
                         and val(rule, '--dport').isdigit()
                         and 30000 <= int(val(rule, '--dport')) <= 32767)
        pilot_return = (val(rule, '-i') == 'eth0' and val(rule, '-o') == 'wg0'
                        and val(rule, '-m') == 'conntrack'
                        and val(rule, '--ctstate') in ('ESTABLISHED,RELATED', 'RELATED,ESTABLISHED')
                        and not val(rule, '-s') and not val(rule, '-d'))
        return pilot_forward or pilot_return
    if val(rule, '-j') == 'SNAT' and table == 'nat' and chain == 'POSTROUTING':
        return (val(rule, '-p') == 'tcp' and net_eq(val(rule, '-s'), '10.77.0.10/32')
                and net_eq(val(rule, '-d'), '10.60.2.10/32')
                and val(rule, '--to-source') == '10.60.1.10'
                and val(rule, '--dport').isdigit()
                and 30000 <= int(val(rule, '--dport')) <= 32767)
    return False


def clean_rules(chain, table):
    for rule in rules(chain, table):
        oldjump = val(rule, '-j') in ALLOWED_OLD
        if oldjump or is_fixed(rule, chain, table):
            cmd('-D', chain, *rule[2:], table=table)
            print('Removed', table, ' '.join(rule))


def main():
    for t, chain in [('filter', 'FORWARD'), ('nat', 'PREROUTING'), ('nat', 'POSTROUTING')]:
        clean_rules(chain, t)
    for t, name in [('filter', 'CTF_VIP_FWD'), ('filter', 'AC_VIP_FORWARD'),
                    ('nat', 'CTF_VIP_DNAT'), ('nat', 'AC_VIP_DNAT'),
                    ('nat', 'CTF_VIP_SNAT'), ('nat', 'AC_VIP_SNAT')]:
        if cmd('-S', name, table=t, check=False).returncode == 0:
            cmd('-F', name, table=t)
            cmd('-X', name, table=t)
            print('Removed old pilot chain', name)


if __name__ == '__main__':
    main()
