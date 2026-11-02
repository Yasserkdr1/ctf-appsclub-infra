resource "azurerm_network_interface" "this" {
  name                  = "nic-${var.name}"
  location              = var.location
  resource_group_name   = var.resource_group_name
  ip_forwarding_enabled = var.enable_ip_forwarding
  tags                  = var.tags

  ip_configuration {
    name                          = "primary"
    subnet_id                     = var.subnet_id
    private_ip_address_allocation = "Static"
    private_ip_address            = var.private_ip
    public_ip_address_id          = var.public_ip_id
    primary                       = true
  }
}

resource "azurerm_linux_virtual_machine" "this" {
  name                            = var.name
  computer_name                   = var.name
  location                        = var.location
  resource_group_name             = var.resource_group_name
  size                            = var.vm_size
  admin_username                  = "ctfadmin"
  disable_password_authentication = true
  network_interface_ids           = [azurerm_network_interface.this.id]
  tags                            = var.tags

  admin_ssh_key {
    username   = "ctfadmin"
    public_key = var.ssh_public_key
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
    disk_size_gb         = var.disk_size_gb
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "ubuntu-24_04-lts"
    sku       = "server"
    version   = "latest"
  }
}
