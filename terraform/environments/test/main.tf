locals {
  prefix = "ctf-appsclub-test"
  tags = {
    project     = "ctf-appsclub"
    environment = "test"
    managed_by  = "terraform"
  }
}

resource "azurerm_resource_group" "this" {
  name     = "rg-${local.prefix}"
  location = var.location
  tags     = local.tags
}

module "network" {
  source              = "../../modules/network"
  name_prefix         = local.prefix
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  admin_cidr          = var.admin_cidr
  deploy_vms          = var.deploy_vms
  ctfd_private_ip     = "10.60.1.10"
  tags                = local.tags
}

module "ctfd" {
  count                = var.deploy_vms ? 1 : 0
  source               = "../../modules/vm"
  name                 = "vm-ctfd-test"
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  subnet_id            = module.network.ctfd_subnet_id
  private_ip           = "10.60.1.10"
  public_ip_id         = module.network.ctfd_public_ip_id
  enable_ip_forwarding = true
  vm_size              = var.ctfd_vm_size
  disk_size_gb         = 64
  ssh_public_key       = var.admin_ssh_public_key
  tags                 = local.tags
}

module "worker" {
  count                = var.deploy_vms ? 1 : 0
  source               = "../../modules/vm"
  name                 = "vm-worker-test"
  resource_group_name  = azurerm_resource_group.this.name
  location             = azurerm_resource_group.this.location
  subnet_id            = module.network.worker_subnet_id
  private_ip           = "10.60.2.10"
  public_ip_id         = null
  enable_ip_forwarding = false
  vm_size              = var.worker_vm_size
  disk_size_gb         = 128
  ssh_public_key       = var.admin_ssh_public_key
  tags                 = local.tags
  depends_on           = [module.network]
}
