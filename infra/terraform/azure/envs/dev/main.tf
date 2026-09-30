provider "azurerm" {
  features {}
}

locals {
  tags = {
    project     = "ai-team"
    env         = var.env
    owner       = var.owner
    cost_center = var.cost_center
  }
}

module "foundry" {
  source = "../../modules/foundry"
  env    = var.env
}

module "model_deployment" {
  source = "../../modules/model_deployment"
  env    = var.env
}

module "container_apps_job" {
  source = "../../modules/container_apps_job"
  env    = var.env
}

module "identity_rbac" {
  source = "../../modules/identity_rbac"
  env    = var.env
}

module "observability" {
  source = "../../modules/observability"
  env    = var.env
}

module "key_vault" {
  source = "../../modules/key_vault"
  env    = var.env
}

module "artifacts_storage" {
  source = "../../modules/artifacts_storage"
  env    = var.env
}

module "budget" {
  source             = "../../modules/budget"
  env                = var.env
  location           = var.location
  monthly_budget_usd = var.monthly_budget_usd
  alert_email        = var.alert_email
  tags               = local.tags
}
