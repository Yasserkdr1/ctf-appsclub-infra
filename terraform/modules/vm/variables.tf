variable "name" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "subnet_id" { type = string }
variable "private_ip" { type = string }
variable "public_ip_id" {
  type    = string
  default = null
}
variable "enable_ip_forwarding" { type = bool }
variable "vm_size" { type = string }
variable "disk_size_gb" { type = number }
variable "ssh_public_key" { type = string }
variable "tags" { type = map(string) }
