terraform {
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "4.40.0"
    }
  }

  # Default is local. Copy backend.hcl.example to backend.hcl (not committed)
  # for an Azure Storage backend.
  backend "local" {}
}
