# Architecture Microservices avec Authentification JWT

## 📋 Description du Projet

Ce projet implémente une architecture microservices avec authentification JWT pour une application Flask. L'architecture comprend 4 services indépendants communiquant via HTTP et un API Gateway centralisant toutes les requêtes.

## 🏗️ Architecture

### Schéma de l'Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Application Web (app.py)                │
│                      Port: 5000                             │
│              Interface utilisateur Flask                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        │ HTTP Requests
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway                              │
│                    Port: 5004                               │
│  • Validation des tokens JWT                                │
│  • Routage vers les microservices                           │
│  • Gestion des erreurs                                      │
└───────┬───────────────┬───────────────┬─────────────────────┘
        │               │               │
        │               │               │
        ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Auth Service │ │ User Service │ │Orders Service│
│ Port: 5001   │ │ Port: 5002   │ │ Port: 5003   │
│              │ │              │ │              │
│ • Login      │ │ • CRUD Users │ │ • Orders     │
│ • JWT Gen    │ │ • Profiles   │ │ • History    │
│ • Verify     │ │              │ │              │
└──────────────┘ └──────────────┘ └──────────────┘
```

### Services

#### 1. **Auth Service** (Port 5001)
- **Rôle**: Gestion de l'authentification et des tokens JWT
- **Endpoints**:
  - `POST /auth/login` - Authentification et génération de tokens (access + refresh)
  - `POST /auth/verify` - Vérification de la validité d'un token
  - `POST /auth/refresh` - Renouvellement de l'access token avec le refresh token
  - `POST /auth/logout` - Révoque un refresh token
  - `GET /health` - Vérification de santé du service
- **Base de données**: `users.db` (table `users` et `refresh_tokens`)
- **Tokens**:
  - Access Token: durée de vie 15 minutes
  - Refresh Token: durée de vie 7 jours

#### 2. **User Service** (Port 5002)
- **Rôle**: Gestion des profils utilisateurs (CRUD)
- **Endpoints**:
  - `GET /users/profile` - Récupération du profil utilisateur
  - `GET /users` - Liste de tous les utilisateurs (admin uniquement)
  - `POST /users` - Création d'un nouvel utilisateur (admin uniquement)
  - `GET /users/<id>` - Récupération d'un utilisateur par ID
  - `PUT /users/<id>` - Mise à jour d'un utilisateur
  - `DELETE /users/<id>` - Suppression d'un utilisateur (admin uniquement)
  - `GET /health` - Vérification de santé du service
- **Base de données**: `users.db` (table `users`)

#### 3. **Orders Service** (Port 5003)
- **Rôle**: Gestion des commandes et de l'historique
- **Endpoints**:
  - `POST /orders` - Création d'une commande
  - `GET /orders` - Liste des commandes de l'utilisateur
  - `GET /orders/history` - Historique des commandes
  - `GET /orders/<id>` - Récupération d'une commande par ID
  - `GET /health` - Vérification de santé du service
- **Base de données**: `orders.db` (table `orders`)

#### 4. **API Gateway** (Port 5004)
- **Rôle**: Point d'entrée unique, validation des tokens, routage
- **Endpoints**:
  - `POST /gateway/auth/login` - Route vers Auth Service
  - `POST /gateway/auth/verify` - Route vers Auth Service
  - `GET /gateway/users/*` - Routes vers User Service
  - `GET /gateway/orders/*` - Routes vers Orders Service
  - `POST /gateway/orders/*` - Routes vers Orders Service
  - `GET /health` - Vérification de santé du Gateway

## 🚀 Installation et Démarrage

### Prérequis

- Python 3.8+
- pip

### Installation

1. **Cloner ou télécharger le projet**

2. **Créer un environnement virtuel** (recommandé):
```powershell
python -m venv .venv
```

3. **Activer l'environnement virtuel**:
```powershell
# Windows PowerShell
.venv\Scripts\activate

# Windows CMD
.venv\Scripts\activate.bat

# Linux/Mac
source .venv/bin/activate
```

4. **Installer les dépendances**:
```powershell
pip install -r requirements.txt
```

### Démarrage des Services

#### Option 1: Démarrage automatique (Recommandé)

```powershell
# Double-cliquez sur TOUT_DEMARRER.bat
# OU exécutez dans PowerShell:
.\TOUT_DEMARRER.bat
```

Ce script va:
- Arrêter les anciens services sur les ports 5000-5003
- Initialiser les bases de données
- Démarrer les 4 microservices dans des fenêtres séparées

#### Option 2: Démarrage manuel

Dans 4 terminaux séparés:

**Terminal 1 - Auth Service:**
```powershell
cd auth_service
python app.py
```

**Terminal 2 - User Service:**
```powershell
cd user_service
python app.py
```

**Terminal 3 - Orders Service:**
```powershell
cd orders_service
python app.py
```

**Terminal 4 - API Gateway:**
```powershell
cd gateway
python app.py
```

### Démarrage de l'Application Web

Dans un nouveau terminal:

```powershell
# Activer l'environnement virtuel si pas déjà fait
.venv\Scripts\activate

# Démarrer l'application
python app.py
```

L'application sera accessible sur: **http://localhost:5000/**

## 🧪 Tests Manuels

1. **Vérifier la santé des services**:
```powershell
# Auth Service
Invoke-RestMethod -Uri "http://localhost:5001/health"

# User Service
Invoke-RestMethod -Uri "http://localhost:5002/health"

# Orders Service
Invoke-RestMethod -Uri "http://localhost:5003/health"

# Gateway
Invoke-RestMethod -Uri "http://localhost:5004/health"
```

2. **Tester l'authentification via Gateway**:
```powershell
$body = @{
    username = "admin"
    password = "admin123"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:5004/gateway/auth/login" -Method POST -Body $body -ContentType "application/json"
```

## 👀 Observer les Microservices en Action

### Dans les Terminaux

Chaque service affiche ses requêtes en temps réel dans son terminal:

**Auth Service (port 5001):**
```
127.0.0.1 - - [13/Nov/2025 14:00:00] "POST /auth/login HTTP/1.1" 200 -
127.0.0.1 - - [13/Nov/2025 14:00:05] "POST /auth/verify HTTP/1.1" 200 -
```

**User Service (port 5002):**
```
127.0.0.1 - - [13/Nov/2025 14:00:10] "GET /users HTTP/1.1" 200 -
127.0.0.1 - - [13/Nov/2025 14:00:15] "GET /users/profile HTTP/1.1" 200 -
```

**Orders Service (port 5003):**
```
127.0.0.1 - - [13/Nov/2025 14:00:20] "GET /orders/history HTTP/1.1" 200 -
127.0.0.1 - - [13/Nov/2025 14:00:25] "POST /orders HTTP/1.1" 201 -
```

**Gateway (port 5004):**
```
127.0.0.1 - - [13/Nov/2025 14:00:00] "POST /gateway/auth/login HTTP/1.1" 200 -
127.0.0.1 - - [13/Nov/2025 14:00:05] "GET /gateway/users/profile HTTP/1.1" 200 -
127.0.0.1 - - [13/Nov/2025 14:00:10] "GET /gateway/orders/history HTTP/1.1" 200 -
```

### Exemple de Flux Complet

**Scénario: Connexion d'un utilisateur**

1. L'utilisateur entre ses identifiants sur le site (port 5000)
2. Le site envoie `POST /gateway/auth/login` au Gateway (port 5004)
3. Le Gateway route vers Auth Service: `POST /auth/login` (port 5001)
4. Auth Service génère un token JWT et le retourne
5. Le Gateway retourne le token au site
6. Le site stocke le token dans la session

**Scénario: Consultation de l'historique**

1. L'utilisateur clique sur "Historique" sur le site
2. Le site envoie `GET /gateway/orders/history` avec le token au Gateway
3. Le Gateway vérifie le token via Auth Service: `POST /auth/verify`
4. Si valide, le Gateway route vers Orders Service: `GET /orders/history`
5. Orders Service retourne l'historique
6. Le Gateway retourne l'historique au site
7. Le site affiche l'historique

## 🔑 Comptes de Test

Les comptes suivants sont créés automatiquement lors de l'initialisation:

- **Admin**: `admin` / `admin123` (rôle: admin)
- **Utilisateur 1**: `user1` / `password1` (rôle: user)
- **Utilisateur 2**: `maxim` / `maxim` (rôle: user)

## 📁 Structure du Projet

```
.
├── app.py                      # Application web principale (port 5000)
├── init_db.py                  # Script d'initialisation des bases de données
├── requirements.txt            # Dépendances Python
├── TOUT_DEMARRER.bat          # Script de démarrage des microservices
├── README.md                   # Documentation du projet
│
├── auth_service/
│   ├── app.py                 # Service d'authentification (port 5001)
│   └── requirements.txt
│
├── user_service/
│   ├── app.py                 # Service de gestion des utilisateurs (port 5002)
│   └── requirements.txt
│
├── orders_service/
│   ├── app.py                 # Service de gestion des commandes (port 5003)
│   └── requirements.txt
│
├── gateway/
│   ├── app.py                 # API Gateway (port 5004)
│   └── requirements.txt
│
├── templates/                 # Templates HTML Flask
│   ├── base.html
│   ├── login.html
│   ├── index.html
│   ├── historique.html
│   ├── liste_utilisateurs.html
│   ├── ajouter_utilisateur.html
│   ├── banque.html
│   └── confirmation.html
│
├── users.db                   # Base de données SQLite (utilisateurs) - créée automatiquement
└── orders.db                  # Base de données SQLite (commandes) - créée automatiquement
```

## 🔧 Configuration

Les URLs des services peuvent être configurées via des variables d'environnement:

```powershell
$env:AUTH_SERVICE_URL="http://localhost:5001"
$env:USER_SERVICE_URL="http://localhost:5002"
$env:ORDERS_SERVICE_URL="http://localhost:5003"
$env:GATEWAY_URL="http://localhost:5004"
```

Par défaut, les services utilisent les ports suivants:
- Application Web: **5000**
- Auth Service: **5001**
- User Service: **5002**
- Orders Service: **5003**
- API Gateway: **5004**

## 📚 Technologies Utilisées

- **Flask**: Framework web Python
- **PyJWT**: Génération et vérification de tokens JWT
- **SQLite**: Bases de données
- **Werkzeug**: Hachage de mots de passe
- **Requests**: Communication HTTP entre services

## ⚠️ Notes Importantes

- Le Gateway utilise le port **5004** car l'application web principale (`app.py`) utilise le port **5000**
- Les services doivent être démarrés avant l'application web
- Les bases de données (`users.db` et `orders.db`) sont créées automatiquement lors de l'initialisation
- En cas d'indisponibilité d'un microservice, l'application web utilise un mécanisme de fallback pour continuer à fonctionner
- **Gestion des tokens JWT**:
  - Lors de la connexion, deux tokens sont générés : access token (15 min) et refresh token (7 jours)
  - Les deux tokens sont stockés dans la session Flask
  - Le système renouvelle automatiquement l'access token lorsqu'il expire (dans les 1 minute avant expiration)
  - Le refresh token permet de rester connecté jusqu'à 7 jours sans re-connexion

## 🐛 Dépannage

### Les services ne démarrent pas

- Vérifiez que les ports 5001-5004 ne sont pas déjà utilisés
- Vérifiez que Python est installé et accessible dans le PATH
- Vérifiez que toutes les dépendances sont installées

### Erreur de connexion entre services

- Vérifiez que tous les services sont démarrés
- Vérifiez les URLs dans `app.py` et `gateway/app.py`
- Vérifiez les logs dans les terminaux de chaque service

### Erreur de base de données

- Supprimez `users.db` et `orders.db` puis relancez `init_db.py`
- Vérifiez les permissions d'écriture dans le répertoire

## 📝 Auteur

Projet réalisé dans le cadre du TP1 - Architecture Microservices
