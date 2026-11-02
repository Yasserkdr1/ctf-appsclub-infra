variable "location" {
  type        = string
  default     = "spaincentral"
  description = "Approved region in the Azure for Students subscription."
  validation {
    condition     = var.location == "spaincentral"
    error_message = "This tested stack must stay in spaincentral."
  }
}

variable "admin_cidr" {
  type        = string
  description = "Public IPv4 /32 of the administrator, for SSH."
}

variable "admin_ssh_public_key" {
  type        = string
  description = "Public SSH key (not a private key)."
}

variable "deploy_vms" {
  type        = bool
  default     = false
  description = "False = network only; true = 2 VMs, 1 public IP and a billed worker NAT gateway."
}

variable "ctfd_vm_size" {
  type    = string
  default = "Standard_D2s_v4"
}

variable "worker_vm_size" {
  type    = string
  default = "Standard_E4ds_v4"
}
