terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "5.100.0"
    }
  }

  # Default is local. Copy backend.hcl.example to backend.hcl (not committed)
  # and pass -backend-config=backend.hcl to use S3 + DynamoDB locking.
  backend "local" {}
}
