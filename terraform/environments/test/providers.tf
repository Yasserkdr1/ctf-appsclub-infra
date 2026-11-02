terraform {
  required_version = ">= 1.8.0, < 2.0.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.70"
    }
  }

  # Credentials and backend identifiers are passed at terraform init.
  backend "azurerm" {}
}

provider "azurerm" {
  features {}
  resource_provider_registrations = "none"
  # Set ARM_SUBSCRIPTION_ID using 'az account show --query id -o tsv'.
}
