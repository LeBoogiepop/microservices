# Rapport TP1 – Première prise en main de Terraform

## 1. Objectifs et Prérequis
L'objectif de ce TP était d'installer et d'initialiser un projet Terraform pour déployer un microservice "catalogue" via Docker. Nous avons suivi le cycle complet `init` -> `plan` -> `apply` -> `destroy` et manipulé des variables et outputs.

**Prérequis validés :**
- Docker est installé et fonctionnel.
- Terraform est installé.
- Environnement de développement configuré (VS Code).

## 2. Étapes du TP

### Étape 1 & 2 : Création du projet et du fichier `main.tf`
Nous avons créé le dossier `tp1-terraform-ecommerce` et le fichier `main.tf` contenant :
- Le provider Docker.
- Les variables `service_name` et `external_port`.
- Le réseau `ecommerce-net`.
- L'image Docker `nginxdemos/hello:latest`.
- Le conteneur utilisant ces éléments.

**Réponses aux questions :**
*   **Variables définies :**
    *   `service_name` : Définit le nom logique du service (par défaut "catalog"). Elle est utilisée pour nommer le conteneur (`${var.service_name}-service`) et définir la variable d'environnement `SERVICE_NAME` à l'intérieur du conteneur.
    *   `external_port` : Définit le port sur la machine hôte (par défaut 8081). Elle est utilisée dans le bloc `ports` (`external = var.external_port`) pour mapper le port 80 du conteneur vers ce port sur l'hôte.
*   **Rôle de `docker_network.ecommerce` :**
    Cette ressource crée un réseau virtuel Docker isolé nommé "ecommerce-net". Elle est définie séparément pour pouvoir être partagée par plusieurs conteneurs (catalogue, panier, commande, etc.). Si elle était définie *dans* le conteneur, elle serait liée à son cycle de vie, ce qui empêcherait d'autres services de s'y connecter facilement ou causerait sa destruction si le conteneur était supprimé.

### Étape 3 : Initialisation (`terraform init`)
La commande `terraform init` a téléchargé le plugin `kreuzwerker/docker` (version ~> 3.0) et a créé le dossier `.terraform` pour stocker ce binaire.

### Étape 4 : Prévisualisation (`terraform plan`)
La commande `terraform plan` a montré que 3 ressources allaient être ajoutées :
1.  `docker_network.ecommerce`
2.  `docker_image.service`
3.  `docker_container.service`

L'output `service_url` a été pré-calculé comme `http://localhost:8081`.

### Étape 5 : Application (`terraform apply`)
L'application a réussi.
- **Vérification :** `docker ps` montre le conteneur `catalog-service` en cours d'exécution sur le port 8081.
- **Test :** L'accès à `http://localhost:8081` affiche bien la page de démonstration Nginx.

### Étape 6 : Expérimentations
1.  **Changement de port :** En modifiant `external_port` à 8082, Terraform détecte un changement qui nécessite le remplacement du conteneur (destroy puis create), car le port est une propriété immuable d'un conteneur Docker en cours d'exécution.
2.  **Changement de nom :** En changeant `service_name` à "cart", le nom du conteneur devient `cart-service` et la variable d'environnement `SERVICE_NAME` change. Terraform recrée également le conteneur.
3.  **Ajout d'un deuxième conteneur :** En dupliquant la ressource `docker_container` pour créer un "panier", Terraform gère les deux conteneurs indépendamment mais les connecte au même réseau `ecommerce-net` existant.

## 3. Questions de réflexion

**1. Terraform vs Docker Compose / Scripts Bash :**
L'utilisation de Terraform apporte une approche **déclarative**.
- Contrairement à un script Bash (impératif) où l'on dit "fais ci, puis fais ça", avec Terraform on décrit l'état final désiré ("je veux un conteneur X"). Terraform calcule seul les actions nécessaires pour atteindre cet état.
- Par rapport à Docker Compose, Terraform est plus généraliste. Il peut gérer Docker mais aussi AWS, Azure, Google Cloud, Kubernetes, etc., le tout avec le même langage (HCL). Cela permet de gérer une infrastructure hybride (ex: base de données sur AWS RDS + application sur Docker local) dans un seul outil.
- Terraform gère un **state** (état) qui garde une trace de ce qui a été créé, permettant de détecter les dérives (drift) et de supprimer proprement les ressources (ce que Bash ne fait pas nativement).

**2. Généralisation pour plusieurs microservices :**
Pour déployer "catalogue", "panier" et "commande" avec un seul `terraform apply`, on pourrait :
- Utiliser des **modules** Terraform : Créer un module générique "microservice" qui prend en paramètre le nom, l'image et le port.
- Appeler ce module 3 fois dans `main.tf` :
  ```hcl
  module "catalog" {
    source = "./modules/microservice"
    service_name = "catalog"
    port = 8081
  }
  module "cart" {
    source = "./modules/microservice"
    service_name = "cart"
    port = 8082
  }
  # ...
  ```
- Ou utiliser `for_each` sur la ressource `docker_container` avec une variable map définissant tous les services et leurs ports.
