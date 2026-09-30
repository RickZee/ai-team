resource "azurerm_resource_group" "this" {
  name     = "rg-ai-team-${var.env}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_consumption_budget_resource_group" "monthly" {
  name              = "ai-team-${var.env}"
  resource_group_id = azurerm_resource_group.this.id
  amount            = var.monthly_budget_usd
  time_grain        = "Monthly"

  time_period {
    start_date = "2026-10-01T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 50
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }
}
