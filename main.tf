terraform {
  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0.0"
    }
  }
}

provider "docker" {
  host = "npipe:////./pipe/docker_engine"
}

resource "docker_network" "micro_net" {
  name   = "micro_net"
  driver = "bridge"
}

# --- Images ---

resource "docker_image" "web_image" {
  name = "appflasktest-web"
  build {
    context    = "./web_service"
    dockerfile = "Dockerfile"
  }
}

resource "docker_image" "auth_image" {
  name = "appflasktest-auth"
  build {
    context    = "./auth_service"
    dockerfile = "Dockerfile"
  }
}

resource "docker_image" "user_image" {
  name = "appflasktest-user"
  build {
    context    = "./user_service"
    dockerfile = "Dockerfile"
  }
}

resource "docker_image" "orders_image" {
  name = "appflasktest-orders"
  build {
    context    = "./orders_service"
    dockerfile = "Dockerfile"
  }
}

resource "docker_image" "gateway_image" {
  name = "appflasktest-gateway"
  build {
    context    = "./gateway"
    dockerfile = "Dockerfile"
  }
}

# --- Services ---

# Init DB (Exécuté une seule fois)
resource "docker_container" "init_db" {
  name  = "init_db"
  image = docker_image.web_image.image_id
  command = ["python", "init_db.py"]
  
  volumes {
    host_path      = abspath("${path.cwd}/users.db")
    container_path = "/app/users.db"
  }

  networks_advanced {
    name = docker_network.micro_net.name
  }
  
  restart = "no"
}

# Auth Service
resource "docker_container" "auth_service" {
  name  = "auth_service"
  image = docker_image.auth_image.image_id
  
  env = [
    "JWT_SECRET_KEY=super-secret-key",
    "FLASK_ENV=production"
  ]
  
  ports {
    internal = 5001
    external = 5001
  }
  
  volumes {
    host_path      = abspath("${path.cwd}/users.db")
    container_path = "/app/users.db"
  }

  networks_advanced {
    name = docker_network.micro_net.name
  }
  
  restart = "unless-stopped"
  
  # Terraform gère l'ordre de création, mais ne peut pas attendre nativement la "complétion" d'un conteneur
  depends_on = [docker_container.init_db]
}

# User Service
resource "docker_container" "user_service" {
  name  = "user_service"
  image = docker_image.user_image.image_id
  
  env = [
    "FLASK_ENV=production"
  ]
  
  ports {
    internal = 5002
    external = 5002
  }
  
  volumes {
    host_path      = abspath("${path.cwd}/users.db")
    container_path = "/app/users.db"
  }

  networks_advanced {
    name = docker_network.micro_net.name
  }
  
  restart = "unless-stopped"
  
  depends_on = [docker_container.init_db]
}

# Orders Service
resource "docker_container" "orders_service" {
  name  = "orders_service"
  image = docker_image.orders_image.image_id
  
  env = [
    "FLASK_ENV=production"
  ]
  
  ports {
    internal = 5003
    external = 5003
  }
  
  volumes {
    host_path      = abspath("${path.cwd}/orders.db")
    container_path = "/app/orders.db"
  }

  networks_advanced {
    name = docker_network.micro_net.name
  }
  
  restart = "unless-stopped"
}

# Gateway
resource "docker_container" "gateway" {
  name  = "gateway"
  image = docker_image.gateway_image.image_id
  
  env = [
    "AUTH_SERVICE_URL=http://auth_service:5001",
    "USER_SERVICE_URL=http://user_service:5002",
    "ORDERS_SERVICE_URL=http://orders_service:5003"
  ]
  
  ports {
    internal = 5004
    external = 5004
  }

  networks_advanced {
    name = docker_network.micro_net.name
  }
  
  restart = "unless-stopped"
  
  depends_on = [
    docker_container.auth_service,
    docker_container.user_service,
    docker_container.orders_service
  ]
}

# Web
resource "docker_container" "web" {
  name  = "web"
  image = docker_image.web_image.image_id
  
  env = [
    "AUTH_SERVICE_URL=http://auth_service:5001",
    "USER_SERVICE_URL=http://user_service:5002",
    "ORDERS_SERVICE_URL=http://orders_service:5003",
    "GATEWAY_URL=http://gateway:5004",
    "FLASK_ENV=production"
  ]
  
  ports {
    internal = 5000
    external = 5000
  }
  
  volumes {
    host_path      = abspath("${path.cwd}/users.db")
    container_path = "/app/users.db"
  }
  
  volumes {
    host_path      = abspath("${path.cwd}/orders.db")
    container_path = "/app/orders.db"
  }

  networks_advanced {
    name = docker_network.micro_net.name
  }
  
  restart = "unless-stopped"
  
  depends_on = [docker_container.gateway]
}
