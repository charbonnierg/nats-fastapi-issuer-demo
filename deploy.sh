#!/usr/bin/env bash


nomad job run nomad/jobs/loki.nomad
nomad job run nomad/jobs/prometheus.nomad
nomad job run nomad/jobs/alertmanager.nomad
nomad job run nomad/jobs/tempo.nomad
nomad job run nomad/jobs/grafana.nomad
nomad job run nomad/jobs/restapi.nomad
