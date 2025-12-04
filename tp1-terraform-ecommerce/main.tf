terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {}

variable "service_name" {
  type        = string
  description = "Nom du microservice"
  default     = "catalog"
}

variable "external_port" {
  type        = number
  description = "Port exposé sur la machine hôte"
  default     = 8081
}

resource "docker_network" "ecommerce" {
  name = "ecommerce-net"
}

resource "docker_image" "service" {
  name         = "nginxdemos/hello:latest"
  keep_locally = true
}

resource "docker_container" "service" {
  name  = "${var.service_name}-service"
  image = docker_image.service.image_id

  networks_advanced {
    name = docker_network.ecommerce.name
  }

  ports {
    internal = 80
    external = var.external_port
  }

  env = [
    "SERVICE_NAME=${var.service_name}",
    "ENVIRONMENT=dev"
  ]
}

output "service_url" {
  value = "http://localhost:${var.external_port}"
}
