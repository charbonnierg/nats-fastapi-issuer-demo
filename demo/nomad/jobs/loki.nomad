job "loki" {
  datacenters = ["dc1"]
  type = "service"

  update {
    stagger = "30s"
    max_parallel = 1
  }

  group "loki" {
    restart {
      attempts = 10
      interval = "5m"
      delay = "10s"
      mode = "delay"
    }
    network {
      port "http" {
        static = 3100
      }
    }
    task "loki" {
      driver = "docker"
      config {
        image = "grafana/loki:2.5.0"
        args = ["-config.file=/etc/loki/local-config.yaml"]
        ports = ["http"]
      }
    }
    service {
      name = "grafana-loki"
      port = "http"
    }
  }
}