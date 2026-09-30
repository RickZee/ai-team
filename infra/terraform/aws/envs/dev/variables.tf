variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "env" {
  type    = string
  default = "dev"
}

variable "owner" {
  type    = string
  default = "rick"
}

variable "cost_center" {
  type    = string
  default = "ai-team"
}

variable "monthly_budget_usd" {
  type    = number
  default = 25
}

variable "alert_email" {
  type    = string
  default = "owner@example.com"
}
