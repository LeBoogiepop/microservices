# TD1 – Comprendre Terraform et l’IaC
## Fil rouge : site e-commerce en microservices (ESME)

### 4. Questions – Partie 1 : Lecture du code

#### 1. Q1. Identification des blocs

*   **Types de blocs et rôles :**
    *   `terraform { ... }` : Bloc de configuration globale de Terraform, utilisé ici pour définir les providers requis et leurs versions.
    *   `provider "..." { ... }` : Configure un fournisseur spécifique (ici Docker) pour permettre à Terraform d'interagir avec son API.
    *   `resource "..." "..." { ... }` : Définit un élément d'infrastructure à créer et gérer (réseau, image, conteneur).
    *   `output "..." { ... }` : Définit des valeurs de sortie à afficher après l'exécution ou à utiliser par d'autres modules.

*   **Rôle du bloc `terraform { required_providers { ... } }` :**
    Dans un projet partagé, ce bloc assure que tous les membres de l'équipe utilisent les mêmes versions des providers, garantissant ainsi la reproductibilité et évitant les conflits de compatibilité.

*   **Rôle du bloc `provider "docker"` :**
    Il indique à Terraform d'initialiser le plugin Docker, permettant ainsi la création et la gestion de ressources Docker (conteneurs, images, réseaux) sur la machine locale ou un hôte distant.

#### 2. Q2. Réseau, image et conteneur

*   **Ressource réseau :**
    C'est la ressource `resource "docker_network" "ecommerce"` qui crée le réseau.
    Le nom vu par `docker network ls` sera `ecommerce-net` (défini par l'argument `name = "ecommerce-net"`).

*   **Relation image/conteneur :**
    Le conteneur a besoin d'une image pour être instancié. Dans le code, `image = docker_image.catalog.image_id` crée une dépendance explicite : Terraform doit d'abord récupérer ou construire l'image (`docker_image.catalog`) avant de pouvoir créer le conteneur (`docker_container.catalog`) qui l'utilise.

*   **Connexion au réseau :**
    Le conteneur est connecté via le bloc `networks_advanced { name = docker_network.ecommerce.name }`.
    Si la ressource `docker_network.ecommerce` était supprimée, Terraform détruirait d'abord le conteneur (car il dépend du réseau), puis le réseau lui-même. Si on relance un `apply` sans le réseau, la création du conteneur échouerait car le réseau requis n'existerait plus.

#### 3. Q3. Ports, variables d’environnement et output

*   **Ports :**
    `internal = 5001` est le port écouté par l'application *dans* le conteneur. `external = 8081` est le port exposé sur la machine hôte.
    L'URL pour tester est : `http://localhost:8081`.

*   **Variables d'environnement :**
    Elles servent à configurer le comportement de l'application sans changer son code (principe des 12-factor apps).
    *Exemples pour le fil rouge :* `DB_HOST` (adresse de la base de données), `DB_PASSWORD` (mot de passe), ou `PAYMENT_GATEWAY_URL`.

*   **Intérêt de l'output :**
    Dans un pipeline CI/CD, cela permet de récupérer dynamiquement l'URL de l'application déployée pour lancer des tests automatisés (e.g., `curl $(terraform output -raw catalog_url)`). Pour la documentation, cela donne une information claire à l'utilisateur sur comment accéder au service.

---

### 5. Questions – Partie 2 : Terraform, microservices et IaC

#### 4. Q4. Approche déclarative vs approche impérative

*   **Comparaison :**
    Avec `docker run` (impératif), on donne une liste d'ordres à exécuter séquentiellement ("télécharge l'image", "crée le réseau", "lance le conteneur"). Si on relance la commande, on risque de créer des doublons ou des erreurs.
    Avec Terraform (déclaratif), on décrit l'état *final* souhaité ("je veux un conteneur qui tourne avec cette image"). Terraform se débrouille pour atteindre cet état (créer s'il n'existe pas, ne rien faire s'il est déjà là, modifier si la config a changé).

*   **Avantages de l'approche déclarative :**
    1.  **Idempotence :** On peut appliquer le même code plusieurs fois, le résultat sera toujours le même état final, sans effets de bord indésirables.
    2.  **Lisibilité/Documentation :** Le fichier décrit l'architecture telle qu'elle doit être, servant de documentation à jour.
    3.  **Gestion des dérives (Drift detection) :** L'outil peut détecter si l'infrastructure réelle a divergé de la configuration et proposer de la corriger.

*   **Classification :**
    *   **Terraform :** Déclaratif (on décrit le résultat attendu).
    *   **docker-compose :** Plutôt déclaratif (on décrit les services dans un YAML).
    *   **Script Bash :** Impératif (on liste les étapes d'exécution).

#### 5. Q5. State Terraform et travail en équipe

*   **Le State (`terraform.tfstate`) :**
    C'est un fichier JSON qui mappe les ressources définies dans le code Terraform vers les ressources réelles existant dans l'infrastructure (ici, les ID des conteneurs Docker). Il contient l'état actuel de l'infrastructure vue par Terraform.

*   **Problèmes si local :**
    Si le fichier reste sur le PC d'un seul membre, les autres membres de l'équipe ne savent pas quel est l'état de l'infrastructure. S'ils lancent `terraform apply`, Terraform pensera que rien n'existe et tentera de tout recréer, causant des conflits (noms déjà pris) ou des duplications.

*   **Avantages du backend distant (S3) :**
    1.  **Partage de l'état :** Toute l'équipe accède à la même source de vérité sur l'état de l'infrastructure.
    2.  **Verrouillage (Locking) :** Empêche deux personnes de modifier l'infrastructure en même temps (ce qui corromprait le state).

---

### 6. Questions – Partie 3 : Extension à plusieurs microservices

#### 6. Q6. Modélisation Terraform

*   **Ressources supplémentaires :**
    Pour ajouter "panier" et "commande", il faudrait :
    *   2 ressources `docker_image` supplémentaires (ex: `image_cart`, `image_order`).
    *   2 ressources `docker_container` supplémentaires (ex: `container_cart`, `container_order`).
    *   Le réseau `docker_network` reste unique et partagé.

*   **Schéma logique :**
    ```mermaid
    graph TD
        Net[Réseau: ecommerce-net]
        
        subgraph Conteneurs
            C1[Catalog Service]
            C2[Cart Service]
            C3[Order Service]
        end
        
        C1 -- connect --o Net
        C2 -- connect --o Net
        C3 -- connect --o Net
    ```
    *Cohérence :* Terraform maintient le graphe de dépendances. Il sait que le réseau doit exister pour que les conteneurs s'y connectent. Si on modifie le réseau, Terraform sait qu'il doit potentiellement mettre à jour les connexions des 3 conteneurs.

*   **Variables pour environnements (dev/prod) :**
    1.  `variable "environment" { type = string }` : Pour suffixer les noms de ressources ou passer la variable d'env `ENVIRONMENT` (ex: "dev", "prod").
    2.  `variable "app_port" { type = number }` : Pour changer le port exposé selon l'environnement (ex: 8080 en dev, 80 en prod).
