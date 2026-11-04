# AppsClub Kubernetes Bootstrap

## Infrastructure ownership

Ansible installs K3s using `install-k3s.yml`.

Ansible owns the following static resources through
`bootstrap-ctf-system.yml`:

- Namespace `ctf-system` and Pod Security labels
- NetworkPolicy `default-deny`
- NetworkPolicy `allow-dns`
- Service `chall-manager-private`, NodePort 31080
- NetworkPolicy `allow-ctfd-to-chall-manager`

Chall-Manager's Pulumi deployment owns its Deployment,
generated ServiceAccount and associated dynamic resources.

Challenge instances and their Kubernetes isolation policies
are managed through Chall-Manager/Pulumi in `cm-target-daunsoix`.

Do not use Ansible to overwrite Pulumi-managed resources.

## Validation

From the repository:

    cd ansible
    ansible-playbook -i inventory.ini \
      playbooks/bootstrap-ctf-system.yml --syntax-check

    ansible-playbook -i inventory.ini \
      playbooks/bootstrap-ctf-system.yml

The second command performs a Kubernetes server-side dry-run.

## Applying changes

After reviewing the expected changes:

    ansible-playbook -i inventory.ini \
      playbooks/bootstrap-ctf-system.yml \
      -e ctf_system_apply=true

Never apply changes to active security policies without review.

## Security considerations

- TCP 31080 is a NodePort, not a public Internet service.
- Azure NSG rules and host firewalls must restrict access.
- The CTFd gateway currently uses 10.60.1.10.
- Never expose the Kubernetes API publicly.
- Keep the default-deny NetworkPolicy enabled.
- The old `chall-manager` ServiceAccount may still exist
  in the cluster; cleanup is a separate operation.
- The old `ctf-test` namespace may also still exist.
