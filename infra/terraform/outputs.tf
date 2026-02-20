output "api_service_url" {
  description = "Deployed API Cloud Run URL."
  value       = google_cloud_run_v2_service.api.uri
}

output "web_service_url" {
  description = "Deployed web Cloud Run URL."
  value       = google_cloud_run_v2_service.web.uri
}

output "api_service_account_email" {
  description = "Service account used by API Cloud Run service."
  value       = google_service_account.api.email
}

output "web_service_account_email" {
  description = "Service account used by web Cloud Run service."
  value       = google_service_account.web.email
}
