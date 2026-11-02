# Backend bootstrap

Run `bash scripts/bootstrap-tfstate.sh` from the repository root after Azure CLI login,
with the subscription owner's permission. This makes an Azure Storage account
for Terraform state OUTSIDE the Terraform-managed test resource group.

Grant Storage Blob Data Contributor (data plane) on the storage account to the
logged-in Azure user. Owner must grant this role, as Contributor cannot assign RBAC.

Do not store credentials in git. Do not destroy the tfstate RG until all workloads
are destroyed and their state is archived.
