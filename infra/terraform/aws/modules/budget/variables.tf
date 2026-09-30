variable "env" {
  type    = string
  default = "dev"
}

variable "monthly_budget_usd" {
  type    = number
  default = 25
}

variable "alert_email" {
  type        = string
  description = "Budget alert recipient. Not a secret."
  default     = "owner@example.com"
}
