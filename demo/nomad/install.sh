#!/usr/bin/env bash

# See: https://learn.hashicorp.com/tutorials/nomad/get-started-install


function addAptKey() {
    curl -fsSL https://apt.releases.hashicorp.com/gpg | apt-key add -
}

function addAptRepository {
    apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
}

function install {
    apt-get update
    apt-get install nomad consul
}

function main {
    addAptKey
    addAptRepository
    install
}

main
