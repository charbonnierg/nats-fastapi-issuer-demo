job "restapi" {
  datacenters = ["dc1"]
  type = "service"

  update {
    stagger = "30s"
    max_parallel = 1
  }

  group "restapi" {
    restart {
      attempts = 10
      interval = "5m"
      delay = "10s"
      mode = "delay"
    }
    network {
      port "http" {}
    }
    task "restapi" {
      driver = "docker"
      config {
        image = "quara/demo-app:fastapi"
        ports = ["http"]
        logging {
          type = "loki"
          config {
            loki-url = "http://${NOMAD_IP_http}:3100/loki/api/v1/push"
            loki-external-labels = "instance={{.ID}}.{{.Name}},host=${NOMAD_IP_http},service=restapi"
          }
      }
      }
      env {
        TELEMETRY_METRICS_ENABLED = "1"
        TELEMETRY_TRACES_ENABLED = "1"
        TELEMETRY_TRACES_EXPORTER = "otlp"
        OTEL_EXPORTER_OTLP_ENDPOINT = "http://${NOMAD_IP_http}:4317/v1/traces"
        SERVER_DEBUG = "1"
        LOGGING_LEVEL = "DEBUG"
        LOGGING_COLORS = "0"
        LOGGING_RENDERER = "json"
        SERVER_HOST = "0.0.0.0"
        SERVER_PORT = "${NOMAD_PORT_http}"
      }

      resources {
        cpu    = 1000
        memory = 256
      }

      service {
        name = "restapi"
        port = "http"
      }
    }
  }
}