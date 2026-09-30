provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      project     = "ai-team"
      env         = var.env
      owner       = var.owner
      cost_center = var.cost_center
    }
  }
}

module "ecr_repo" {
  source = "../../modules/ecr_repo"
  env    = var.env
}

module "agentcore_runtime" {
  source = "../../modules/agentcore_runtime"
  env    = var.env
}

module "iam_runtime_role" {
  source = "../../modules/iam_runtime_role"
  env    = var.env
}

module "bedrock_guardrail" {
  source = "../../modules/bedrock_guardrail"
  env    = var.env
}

module "observability" {
  source = "../../modules/observability"
  env    = var.env
}

module "artifacts_bucket" {
  source = "../../modules/artifacts_bucket"
  env    = var.env
}

module "budget" {
  source             = "../../modules/budget"
  env                = var.env
  monthly_budget_usd = var.monthly_budget_usd
  alert_email        = var.alert_email
}
