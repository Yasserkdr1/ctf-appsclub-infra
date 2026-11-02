output "ctfd_subnet_id" {
  value = azurerm_subnet.ctfd.id
}

output "worker_subnet_id" {
  value = azurerm_subnet.worker.id
}

output "ctfd_public_ip_id" {
  value = var.deploy_vms ? azurerm_public_ip.ctfd[0].id : null
}

output "ctfd_public_ip" {
  value = var.deploy_vms ? azurerm_public_ip.ctfd[0].ip_address : null
}
