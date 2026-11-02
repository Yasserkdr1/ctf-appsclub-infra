# CTF AppsClub — Infrastructure as Code

## Scope

CTFd (15 teams x 4), 5 static challenges and 3 interactive challenges per team,
up to 45 concurrent isolated instances over a 6-hour event.

* Terraform: Azure VNet, network controls, VMs, NAT.
* Ansible: guest configuration (not yet implemented).
* CTFd + K3s + Chall-Manager + WireGuard: planned, not yet security-validated.

**Do not deploy exploitable CTF challenges until the team-isolation and breakout tests pass.**

## 0. Prerequisites (WSL Ubuntu)

Install Azure CLI, Terraform (1.8+) and SSH separately from their official guides.
Use the subscription Owner's authorization before provisioning anything.

```bash
az login --use-device-code
az account show -o table
export ARM_SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
terraform version
```

Verify the subscription is the intended **Azure for Students** subscription.

## 1. Create the persistent Terraform backend (minor ongoing storage cost)

```bash
bash scripts/bootstrap-tfstate.sh
```

Have the Owner grant the signed-in user `Storage Blob Data Contributor` on the
new storage account. Test the data-plane access as shown by the script.

## 2. Configure the test stack

```bash
cd terraform/environments/test
cp backend.tfbackend.example backend.tfbackend
cp terraform.tfvars.example terraform.tfvars
```

Edit both files; use the state storage account printed by bootstrap, your OWN
public IPv4 /32 and your SSH **public** key. Check the existing VNet CIDRs before
using 10.60.0.0/16. Do not commit either configuration file.

## 3. Safely initialize and preview (NO Azure resources created)

```bash
terraform init -backend-config=backend.tfbackend
terraform fmt -recursive
terraform validate
terraform plan -out=network.tfplan
terraform show network.tfplan
```

The safe default `deploy_vms = false` creates the RG, VNet, 2 subnets, 2 NSGs and rules ONLY after an `apply`. VMs, NAT and public IPs are conditional.

## 4. Deploy network (with owner approval)

```bash
terraform apply network.tfplan
```

## 5. Preview (do not yet apply) the billed 2-VM stack

Edit terraform.tfvars and set `deploy_vms = true`, then:

```bash
terraform plan -out=vms.tfplan
terraform show vms.tfplan
```

Sizes: D2s_v4 (CTFd), E4ds_v4 (worker), 6 regional vCPUs total.
Includes Standard public IP for CTFd and an hourly-billed NAT Gateway for the
private worker VM. Azure SKU availability and current price are NOT guaranteed
by successful plan. The worker has no public IP. Review costs and owner consent
before any VM apply.

## 6. Teardown (irreversible, after backing up CTFd)

```bash
terraform plan -destroy
terraform destroy
```

This destroys resources in this test stack, including VM OS disks and data on them.
It does NOT delete the separate `rg-ctf-tfstate` state storage. Stop/deallocate VMs
between tests to reduce compute charges; disks, public IPs and NAT continue to bill
until deleted.

## Security gates (NOT implemented by Terraform alone)

- CTFd mode Teams, 15 max, 4 members/team.
- Exactly 1 instance per (team, challenge), 45 max, lifetime until CTF end.
- Worker K3s control plane private; do NOT expose port 6443 publicly.
- gVisor compatibility for the actual Pwn binaries must be tested.
- K3s NetworkPolicies, WireGuard per-team ACLs and host firewall must be set
  up and tested before deploying vulnerable challenges.
- Azure metadata access and lateral movement must be blocked from workloads.
- 45-instance full 6h load test is mandatory. Quota does not guarantee performance.

The worker NSG permits CTFd-gateway-initiated SSH, API and Kubernetes NodePorts
only; this is a foundation, NOT full team segregation.
