variable "name_prefix" {
  description = "Prefix for every resource name. The secret is <name_prefix>/app unless secret_name is set."
  type        = string
}

variable "secret_name" {
  description = "Name of the secret. Null uses <name_prefix>/app."
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "CMK that encrypts the secret. Null uses the AWS-managed key (local emulator)."
  type        = string
  default     = null
}

variable "recovery_window_in_days" {
  description = "Days a deleted secret stays recoverable. 0 deletes immediately (local and throwaway environments)."
  type        = number
  default     = 30
}
