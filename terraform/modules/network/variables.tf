variable "name_prefix" { type = string }
variable "resource_group_name" { type = string }
variable "location" { type = string }
variable "admin_cidr" { type = string }
variable "deploy_vms" { type = bool }
variable "ctfd_private_ip" { type = string }
variable "tags" { type = map(string) }
