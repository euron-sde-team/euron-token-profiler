variable "name_prefix" {
  description = "Prefix for every resource name. The alias is alias/<name_prefix>."
  type        = string
}

variable "deletion_window_in_days" {
  description = "Waiting period before a scheduled key deletion completes."
  type        = number
  default     = 30
}

variable "admin_principal_arns" {
  description = "IAM principals allowed to administer (not use) the key. Empty = account root only, which delegates to IAM policies."
  type        = list(string)
  default     = []
}

variable "rotation_period_in_days" {
  description = "Days between automatic rotations of the key material (90 to 2560). Null leaves the period to the service (365 days on AWS); the local emulator does not report a period back, so it passes null to keep repeat applies free of changes."
  type        = number
  default     = 365
}
