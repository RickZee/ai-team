variable "env" {
  type    = string
  default = "dev"
}

variable "location" {
  type    = string
  default = "eastus"
}

variable "monthly_budget_usd" {
  type    = number
  default = 25
}

variable "alert_email" {
  type    = string
  default = "owner@example.com"
}

variable "tags" {
  type = map(string)
}
