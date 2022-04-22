job "grafana" {
  datacenters = ["dc1"]
  type = "service"

  constraint {
    attribute = "${attr.kernel.name}"
    value = "linux"
  }

  update {
    stagger = "30s"
    max_parallel = 1
  }

  group "grafana" {
    network {
      port "http" {}
    }
    restart {
      attempts = 10
      interval = "5m"
      delay = "10s"
      mode = "delay"
    }
    task "grafana" {
      driver = "docker"
      config {
        image = "grafana/grafana-oss"
        ports = ["http"]
      }
      env {
        GF_LOG_LEVEL = "DEBUG"
        GF_LOG_MODE = "console"
        GF_SERVER_HTTP_PORT = "${NOMAD_PORT_http}"
      }
      resources {
        cpu    = 1000
        memory = 256
      }
      service {
        name = "grafana"
        port = "http"
      }
    }
  }
}