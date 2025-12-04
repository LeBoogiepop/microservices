# Projet Microservices E-commerce

Ce projet est une application e-commerce construite avec une architecture microservices en Python (Flask). Il démontre l'utilisation de Docker, Docker Compose et Terraform pour l'orchestration et le déploiement.

## Architecture

L'application est divisée en plusieurs services indépendants :

*   **Web Service (Frontend)** : Interface utilisateur (Flask + Templates HTML).
*   **Auth Service** : Gestion de l'authentification (JWT).
*   **User Service** : Gestion des profils utilisateurs.
*   **Orders Service** : Gestion des commandes.
*   **Gateway** : Point d'entrée unique (API Gateway) qui redirige les requêtes vers les bons services.

## Prérequis

*   Docker Desktop installé et lancé.
*   Terraform (optionnel, pour le déploiement IaC).

## Démarrage Rapide (Docker Compose)

C'est la méthode recommandée pour le développement local.

1.  Clonez ce dépôt.
2.  Lancez l'application :
    ```bash
    docker-compose up --build
    ```
3.  Accédez à l'application sur : [http://localhost:5000](http://localhost:5000)

## Démarrage avec Terraform

Pour simuler un déploiement d'infrastructure :

1.  Construisez les images (si nécessaire) :
    ```bash
    docker-compose build
    ```
2.  Initialisez et appliquez la configuration Terraform :
    ```bash
    terraform init
    terraform apply
    ```
3.  Pour tout arrêter :
    ```bash
    terraform destroy
    ```

## Structure du Projet

*   `/web_service` : Code du frontend.
*   `/auth_service` : Code du service d'authentification.
*   `/user_service` : Code du service utilisateurs.
*   `/orders_service` : Code du service commandes.
*   `/gateway` : Code de l'API Gateway.
*   `docker-compose.yml` : Configuration pour Docker Compose.
*   `main.tf` : Configuration pour Terraform.
