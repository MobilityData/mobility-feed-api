#
# MobilityData 2023
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# This script deploys the Load Balancer's rules are related resources.
# The cloud run service is created with name: mobility-feed-api-${var.environment}
# Module output:
#   feed_api_uri: Main URI of the Feed API

# This make the google project information accessible only keeping the project_id as a parameter in the previous provider resource
data "google_project" "project" {
}

# This resource maps an already created SSL certificate to a terraform state resource.
# The SSL setup is done outside terraform for security reasons.
data "google_compute_ssl_certificate" "existing_ssl_cert" {
  name = "api-${var.environment}-mobilitydatabase"
}

resource "google_compute_security_policy" "policy_rate_limiting" {
  name        = "feed-rate-limiting-${var.environment}"
  description = "Rate limiting"

  rule {
    action   = "throttle"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
    description = "default rule"

    rate_limit_options {
      conform_action = "allow"
      exceed_action  = "deny(429)"

      enforce_on_key = "ALL"

      #     This is a global rate limit threshold limiting all clients
      rate_limit_threshold {
        count        = var.global_rate_limit_req_per_minute
        interval_sec = 60
      }
    }
  }
}

resource "google_compute_region_network_endpoint_group" "feed_cloudrun_neg" {
  name                  = "feed-cloudrun-neg-${var.environment}"
  network_endpoint_type = "SERVERLESS"
  region                = var.gcp_region
  cloud_run {
    service = var.feed_api_name
  }
}

resource "google_compute_backend_service" "feed_api_lb_backend" {
  provider   = google
  name       = "cloudrun-lb-backend-${var.environment}"
  enable_cdn = false
  log_config {
    enable = true
  }
  protocol = "HTTPS"
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.feed_cloudrun_neg.id
  }

  security_policy = google_compute_security_policy.policy_rate_limiting.name

  iap {
    oauth2_client_id     = var.oauth2_client_id
    oauth2_client_secret = var.oauth2_client_secret
  }
  depends_on = [
    google_compute_security_policy.policy_rate_limiting
  ]
}

resource "google_compute_health_check" "http_health_check" {
  name               = "health-check"
  check_interval_sec = 5
  timeout_sec        = 5
  tcp_health_check {
    port = 443
  }
}

resource "google_compute_url_map" "feed_api_url_map" {
  name            = "feed-run-url-map-${var.environment}"
  default_service = google_compute_backend_service.feed_api_lb_backend.id
  host_rule {
    hosts        = ["*"]
    path_matcher = "allpaths"
  }
  path_matcher {
    name = "allpaths"
    default_service = google_compute_backend_service.feed_api_lb_backend.id
    path_rule {
      paths = ["/"]
      service = google_compute_backend_service.feed_api_lb_backend.id
      route_action {
        cors_policy {
          allow_credentials    = true
          allow_headers        = ["*"]
          allow_methods        = ["*"]
          allow_origins        = ["*"]
          max_age              = 10
          disabled             = false
        }
      }
    }
  }
}

resource "google_compute_target_https_proxy" "feed_https_proxy" {
  name             = "feed-proxy"
  url_map          = google_compute_url_map.feed_api_url_map.id
  ssl_certificates = [data.google_compute_ssl_certificate.existing_ssl_cert.id]
}

resource "google_compute_global_address" "feed_http_lb_ipv4" {
  name = "feed-http-lb-ipv4-${var.environment}"
  address_type = "EXTERNAL"
  ip_version = "IPV4"
}

resource "google_compute_global_address" "feed_http_lb_ipv6" {
  name = "feed-http-lb-ipv6-${var.environment}"
  address_type = "EXTERNAL"
  ip_version = "IPV6"
}

resource "google_compute_global_forwarding_rule" "feed_http_lb_rule" {
  name       = "feed-http-lb-rule-${var.environment}"
  target     = google_compute_target_https_proxy.feed_https_proxy.self_link
  port_range = "443"
  ip_address = google_compute_global_address.feed_http_lb_ipv6.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

resource "google_compute_global_forwarding_rule" "feed_http_lb_rule_ipv4" {
  name       = "feed-http-lb-rule-v4-${var.environment}"
  target     = google_compute_target_https_proxy.feed_https_proxy.self_link
  port_range = "443"
  ip_address = google_compute_global_address.feed_http_lb_ipv4.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

