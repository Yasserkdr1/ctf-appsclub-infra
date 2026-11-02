output "resource_group_name" {
  value = azurerm_resource_group.this.name
}

output "ctfd_public_ip" {
  value = module.network.ctfd_public_ip
}

output "ctfd_private_ip" {
  value = var.deploy_vms ? "10.60.1.10" : null
}

output "worker_private_ip" {
  value = var.deploy_vms ? "10.60.2.10" : null
}
