variable "project_id" {
  type        = string
  description = "Target GCP project ID."
}

variable "region" {
  type        = string
  description = "GCP region for Cloud Run services."
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Deployment environment label."
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be one of: development, staging, production."
  }
}

variable "name_prefix" {
  type        = string
  description = "Prefix for infrastructure resources."
  default     = "sat-graph-rag"
}

variable "api_image" {
  type        = string
  description = "Container image for API service."
}

variable "web_image" {
  type        = string
  description = "Container image for web service."
}

variable "api_env" {
  type        = map(string)
  description = "Plain environment variables for API service."
  default     = {}
}

variable "web_env" {
  type        = map(string)
  description = "Plain environment variables for web service."
  default     = {}
}

variable "api_secret_env" {
  type        = map(string)
  description = "Map of API env var names to Secret Manager secret IDs."
  default     = {}
}

variable "web_secret_env" {
  type        = map(string)
  description = "Map of web env var names to Secret Manager secret IDs."
  default     = {}
}

variable "api_allow_unauthenticated" {
  type        = bool
  description = "Whether API service should allow unauthenticated invocation."
  default     = false
}

variable "web_allow_unauthenticated" {
  type        = bool
  description = "Whether web service should allow unauthenticated invocation."
  default     = true
}

variable "api_ingress" {
  type        = string
  description = "Ingress policy for API Cloud Run service."
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "web_ingress" {
  type        = string
  description = "Ingress policy for web Cloud Run service."
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "api_min_instances" {
  type        = number
  description = "Minimum API Cloud Run instances."
  default     = 0
}

variable "api_max_instances" {
  type        = number
  description = "Maximum API Cloud Run instances."
  default     = 10
}

variable "web_min_instances" {
  type        = number
  description = "Minimum web Cloud Run instances."
  default     = 0
}

variable "web_max_instances" {
  type        = number
  description = "Maximum web Cloud Run instances."
  default     = 10
}

variable "api_cpu" {
  type        = string
  description = "CPU limit for API container."
  default     = "1"
}

variable "api_memory" {
  type        = string
  description = "Memory limit for API container."
  default     = "1Gi"
}

variable "web_cpu" {
  type        = string
  description = "CPU limit for web container."
  default     = "1"
}

variable "web_memory" {
  type        = string
  description = "Memory limit for web container."
  default     = "512Mi"
}

variable "vpc_connector" {
  type        = string
  description = "Optional VPC connector for private resource egress."
  default     = null
}

variable "enable_observability_artifacts" {
  type        = bool
  description = "Whether to provision monitoring dashboards and alert policies."
  default     = true
}

variable "monitoring_notification_channel_ids" {
  type        = list(string)
  description = "Notification channel IDs used by alert policies."
  default     = []
}
