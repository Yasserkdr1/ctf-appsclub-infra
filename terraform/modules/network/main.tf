resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.name_prefix}"
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = ["10.60.0.0/16"]
  tags                = var.tags
}

resource "azurerm_subnet" "ctfd" {
  name                            = "snet-ctfd"
  resource_group_name             = var.resource_group_name
  virtual_network_name            = azurerm_virtual_network.this.name
  address_prefixes                = ["10.60.1.0/24"]
  default_outbound_access_enabled = false
}

resource "azurerm_subnet" "worker" {
  name                            = "snet-worker"
  resource_group_name             = var.resource_group_name
  virtual_network_name            = azurerm_virtual_network.this.name
  address_prefixes                = ["10.60.2.0/24"]
  default_outbound_access_enabled = false
}

resource "azurerm_network_security_group" "ctfd" {
  name                = "nsg-ctfd-test"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_network_security_rule" "ctfd_ssh" {
  name                        = "AllowAdminSSH"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "22"
  source_address_prefix       = var.admin_cidr
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.ctfd.name
}

resource "azurerm_network_security_rule" "ctfd_https" {
  name                        = "AllowPublicHTTPS"
  priority                    = 110
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.ctfd.name
}

resource "azurerm_network_security_rule" "ctfd_http" {
  name                        = "AllowPublicHTTP"
  priority                    = 120
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "80"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.ctfd.name
}

resource "azurerm_network_security_rule" "ctfd_wireguard" {
  name                        = "AllowWireGuard"
  priority                    = 130
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Udp"
  source_port_range           = "*"
  destination_port_range      = "51820"
  source_address_prefix       = "Internet"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.ctfd.name
}

resource "azurerm_network_security_group" "worker" {
  name                = "nsg-worker-test"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_network_security_rule" "worker_from_ctfd" {
  name                        = "AllowCTFdGatewayAndControl"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_ranges     = ["22", "6443", "30000-32767"]
  source_address_prefix       = "${var.ctfd_private_ip}/32"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.worker.name
}

resource "azurerm_network_security_rule" "worker_deny_vnet_in" {
  name                        = "DenyOtherVNetInbound"
  priority                    = 200
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "VirtualNetwork"
  destination_address_prefix  = "*"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.worker.name
}

# Reduces lateral movement from a compromised worker to the CTFd subnet.
# Kubernetes NetworkPolicies and host firewalls are still mandatory.
resource "azurerm_network_security_rule" "worker_deny_ctfd_out" {
  name                        = "DenyWorkerInitiatedToCTFd"
  priority                    = 110
  direction                   = "Outbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "10.60.1.0/24"
  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.worker.name
}

resource "azurerm_subnet_network_security_group_association" "ctfd" {
  subnet_id                 = azurerm_subnet.ctfd.id
  network_security_group_id = azurerm_network_security_group.ctfd.id
}

resource "azurerm_subnet_network_security_group_association" "worker" {
  subnet_id                 = azurerm_subnet.worker.id
  network_security_group_id = azurerm_network_security_group.worker.id
}

# A public IP for the CTFd gateway; NO public IP for the worker VM.
resource "azurerm_public_ip" "ctfd" {
  count               = var.deploy_vms ? 1 : 0
  name                = "pip-ctfd-test"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

# Explicit outbound access for private worker (Azure 2026 private subnet defaults).
# NAT Gateway incurs hourly charges until destroyed.
resource "azurerm_public_ip" "worker_nat" {
  count               = var.deploy_vms ? 1 : 0
  name                = "pip-worker-nat-test"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway" "worker" {
  count                   = var.deploy_vms ? 1 : 0
  name                    = "nat-worker-test"
  location                = var.location
  resource_group_name     = var.resource_group_name
  sku_name                = "Standard"
  idle_timeout_in_minutes = 4
  tags                    = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "worker" {
  count                = var.deploy_vms ? 1 : 0
  nat_gateway_id       = azurerm_nat_gateway.worker[0].id
  public_ip_address_id = azurerm_public_ip.worker_nat[0].id
}

resource "azurerm_subnet_nat_gateway_association" "worker" {
  count          = var.deploy_vms ? 1 : 0
  subnet_id      = azurerm_subnet.worker.id
  nat_gateway_id = azurerm_nat_gateway.worker[0].id
  depends_on     = [azurerm_nat_gateway_public_ip_association.worker]
}


# Worker 10.60.2.10 -> Gateway 10.60.1.10:51820/UDP
resource "azurerm_network_security_rule" "worker_wireguard_to_gateway" {
  name      = "AllowWorkerToGatewayWireGuard"
  priority  = 100
  direction = "Outbound"
  access    = "Allow"
  protocol  = "Udp"

  source_port_range      = "*"
  destination_port_range = "51820"

  source_address_prefix      = "10.60.2.10/32"
  destination_address_prefix = "${var.ctfd_private_ip}/32"

  resource_group_name         = var.resource_group_name
  network_security_group_name = azurerm_network_security_group.worker.name

  depends_on = [
    azurerm_network_security_rule.worker_deny_ctfd_out
  ]
}
