locals {
  labels = {
    system      = "sat-graph-rag"
    environment = var.environment
    managed_by  = "terraform"
  }
  api_service_name = "${var.name_prefix}-api-${var.environment}"
  web_service_name = "${var.name_prefix}-web-${var.environment}"
  canary_metric_specs = {
    error_rate_5xx = {
      type         = "custom.googleapis.com/sat/canary/error_rate_5xx"
      display_name = "Canary 5xx Error Rate"
      threshold    = 0.01
      comparison   = "COMPARISON_GT"
      unit         = "1"
    }
    latency_p95_ratio = {
      type         = "custom.googleapis.com/sat/canary/latency_p95_ratio"
      display_name = "Canary P95 Latency Ratio"
      threshold    = 1.2
      comparison   = "COMPARISON_GT"
      unit         = "1"
    }
    auth_failure_ratio = {
      type         = "custom.googleapis.com/sat/canary/auth_failure_ratio"
      display_name = "Canary Auth Failure Ratio"
      threshold    = 2.0
      comparison   = "COMPARISON_GT"
      unit         = "1"
    }
  }
}

resource "google_project_service" "required" {
  for_each = toset([
    "run.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
    "monitoring.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_service_account" "api" {
  account_id   = replace(local.api_service_name, "_", "-")
  display_name = "SAT Graph RAG API ${var.environment}"
}

resource "google_service_account" "web" {
  account_id   = replace(local.web_service_name, "_", "-")
  display_name = "SAT Graph RAG Web ${var.environment}"
}

resource "google_cloud_run_v2_service" "api" {
  name     = local.api_service_name
  location = var.region
  ingress  = var.api_ingress
  labels   = local.labels

  template {
    service_account = google_service_account.api.email

    scaling {
      min_instance_count = var.api_min_instances
      max_instance_count = var.api_max_instances
    }

    containers {
      image = var.api_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = var.api_cpu
          memory = var.api_memory
        }
      }

      dynamic "env" {
        for_each = merge({ APP_ENVIRONMENT = var.environment }, var.api_env)
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.api_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }

    dynamic "vpc_access" {
      for_each = var.vpc_connector == null ? [] : [1]
      content {
        connector = var.vpc_connector
        egress    = "PRIVATE_RANGES_ONLY"
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service" "web" {
  name     = local.web_service_name
  location = var.region
  ingress  = var.web_ingress
  labels   = local.labels

  template {
    service_account = google_service_account.web.email

    scaling {
      min_instance_count = var.web_min_instances
      max_instance_count = var.web_max_instances
    }

    containers {
      image = var.web_image

      ports {
        container_port = 3000
      }

      resources {
        limits = {
          cpu    = var.web_cpu
          memory = var.web_memory
        }
      }

      dynamic "env" {
        for_each = var.web_env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.web_secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "api_public_invoker" {
  count    = var.api_allow_unauthenticated ? 1 : 0
  name     = google_cloud_run_v2_service.api.name
  location = google_cloud_run_v2_service.api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "web_public_invoker" {
  count    = var.web_allow_unauthenticated ? 1 : 0
  name     = google_cloud_run_v2_service.web.name
  location = google_cloud_run_v2_service.web.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_monitoring_metric_descriptor" "canary" {
  for_each = var.enable_observability_artifacts ? local.canary_metric_specs : {}
  project  = var.project_id

  type         = each.value.type
  metric_kind  = "GAUGE"
  value_type   = "DOUBLE"
  unit         = each.value.unit
  display_name = each.value.display_name
  description  = "Canary rollout metric for SAT Graph RAG."

  labels {
    key         = "service"
    value_type  = "STRING"
    description = "Logical service name."
  }
  labels {
    key         = "environment"
    value_type  = "STRING"
    description = "Deployment environment."
  }
}

resource "google_monitoring_alert_policy" "canary_threshold" {
  for_each = var.enable_observability_artifacts ? local.canary_metric_specs : {}
  project  = var.project_id

  display_name = "${local.api_service_name} ${each.key} guard"
  combiner     = "OR"
  enabled      = true

  documentation {
    mime_type = "text/markdown"
    content   = <<-EOT
Canary guard threshold breached for `${each.key}` in `${var.environment}`. Run deployment rollback procedure and investigate error budget impact.
EOT
  }

  conditions {
    display_name = "${each.key} threshold breach"
    condition_threshold {
      filter = join(
        " AND ",
        [
          "resource.type=\"global\"",
          "metric.type=\"${each.value.type}\"",
          "metric.label.environment=\"${var.environment}\"",
          "metric.label.service=\"${local.api_service_name}\"",
        ]
      )
      comparison      = each.value.comparison
      threshold_value = each.value.threshold
      duration        = "0s"

      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }

      trigger {
        count = 1
      }
    }
  }

  notification_channels = var.monitoring_notification_channel_ids

  alert_strategy {
    auto_close = "1800s"
  }

  depends_on = [google_monitoring_metric_descriptor.canary]
}

resource "google_monitoring_dashboard" "api_operability" {
  count   = var.enable_observability_artifacts ? 1 : 0
  project = var.project_id

  dashboard_json = jsonencode({
    displayName = "SAT Graph RAG ${var.environment} Operability"
    gridLayout = {
      columns = "2"
      widgets = [
        {
          title = "Canary 5xx Error Rate"
          xyChart = {
            dataSets = [
              {
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"global\" AND metric.type=\"custom.googleapis.com/sat/canary/error_rate_5xx\" AND metric.label.environment=\"${var.environment}\" AND metric.label.service=\"${local.api_service_name}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }
            ]
          }
        },
        {
          title = "Canary P95 Latency Ratio"
          xyChart = {
            dataSets = [
              {
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"global\" AND metric.type=\"custom.googleapis.com/sat/canary/latency_p95_ratio\" AND metric.label.environment=\"${var.environment}\" AND metric.label.service=\"${local.api_service_name}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }
            ]
          }
        },
        {
          title = "Canary Auth Failure Ratio"
          xyChart = {
            dataSets = [
              {
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"global\" AND metric.type=\"custom.googleapis.com/sat/canary/auth_failure_ratio\" AND metric.label.environment=\"${var.environment}\" AND metric.label.service=\"${local.api_service_name}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_MEAN"
                    }
                  }
                }
              }
            ]
          }
        },
        {
          title = "API Request Rate (Cloud Run)"
          xyChart = {
            dataSets = [
              {
                plotType = "LINE"
                timeSeriesQuery = {
                  timeSeriesFilter = {
                    filter = "resource.type=\"cloud_run_revision\" AND metric.type=\"run.googleapis.com/request_count\" AND resource.label.service_name=\"${local.api_service_name}\""
                    aggregation = {
                      alignmentPeriod  = "60s"
                      perSeriesAligner = "ALIGN_RATE"
                    }
                  }
                }
              }
            ]
          }
        }
      ]
    }
  })

  depends_on = [google_project_service.required]
}
