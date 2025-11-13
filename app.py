from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import os
import pybreaker
import random
import time
import sqlite3
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import requests

app = Flask(__name__)
app.config['SECRET_KEY'] = 'votre-cle-secrete-ici'

# Configuration des microservices
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:5001')
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:5002')
ORDERS_SERVICE_URL = os.getenv('ORDERS_SERVICE_URL', 'http://localhost:5003')
GATEWAY_URL = os.getenv('GATEWAY_URL', 'http://localhost:5004')  # Port différent car app.py utilise 5000

# Configuration de la base de données (partagée avec les microservices)
DATABASE = 'users.db'

def get_db():
    """Connexion à la base de données SQLite avec timeout pour éviter les verrouillages"""
    conn = sqlite3.connect(DATABASE, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données avec la table users"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            jti TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    default_users = [
        ('admin', 'admin123', 'admin@esme.fr', 'admin'),
        ('user1', 'password1', 'user1@esme.fr', 'user'),
        ('maxim', 'maxim', 'maxim@esme.fr', 'user')
    ]
    
    for username, password, email, role in default_users:
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            ''', (username, hashed_password, email, role))
        except sqlite3.IntegrityError:
            pass
    
    conn.commit()
    conn.close()

init_db()

# Configuration du Circuit Breaker
breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name='BankService'
)

compteur_appels_banque = 0
PRODUIT = {'id': 1, 'nom': 'Produit Test', 'prix': 100}

# ========== FONCTIONS POUR APPELER LES MICROSERVICES ==========

def call_auth_service(endpoint, method='GET', data=None):
    """Appelle l'Auth Service via Gateway"""
    try:
        url = f"{GATEWAY_URL}/gateway/auth{endpoint}"
        if method == 'POST':
            response = requests.post(url, json=data, timeout=2)
        else:
            response = requests.get(url, timeout=2)
        return response.json() if response.status_code == 200 else None
    except:
        return None

def call_user_service(endpoint, method='GET', data=None, token=None):
    """Appelle le User Service via Gateway"""
    try:
        url = f"{GATEWAY_URL}/gateway{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=5)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers, timeout=5)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=5)
        else:
            response = requests.get(url, headers=headers, timeout=5)
        # Retourne la réponse même si le status code n'est pas 200 (pour gérer les erreurs)
        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code >= 400:
            return response.json() if response.content else {'message': f'Erreur {response.status_code}'}
        return None
    except Exception as e:
        print(f"Erreur lors de l'appel au User Service: {e}")
        return None

def call_orders_service(endpoint, method='GET', data=None, token=None):
    """Appelle le Orders Service via Gateway"""
    try:
        url = f"{GATEWAY_URL}/gateway{endpoint}"
        headers = {}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        if method == 'POST':
            response = requests.post(url, json=data, headers=headers, timeout=2)
        elif method == 'PUT':
            response = requests.put(url, json=data, headers=headers, timeout=2)
        else:
            response = requests.get(url, headers=headers, timeout=2)
        return response.json() if response.status_code == 200 else None
    except:
        return None

def refresh_access_token():
    """Renouvelle l'access token en utilisant le refresh token"""
    refresh_token = session.get('refresh_token')
    if not refresh_token:
        return False
    
    try:
        response = requests.post(
            f"{GATEWAY_URL}/gateway/auth/refresh",
            json={"refresh_token": refresh_token},
            timeout=2
        )
        if response.status_code == 200:
            data = response.json()
            session['jwt_token'] = data['access_token']
            session['refresh_token'] = data.get('refresh_token', refresh_token)  # Met à jour si nouveau refresh token
            return True
    except:
        pass
    return False

def get_user_token():
    """Récupère le token JWT de l'utilisateur connecté depuis la session.
    Vérifie et renouvelle automatiquement le token s'il est expiré."""
    access_token = session.get('jwt_token')
    if not access_token:
        return None
    
    # Vérifie si le token est expiré en le décodant
    try:
        payload = jwt.decode(access_token, app.config['SECRET_KEY'], algorithms=['HS256'], options={"verify_exp": False})
        exp = payload.get('exp', 0)
        import time
        # Si le token expire dans moins de 1 minute, on le renouvelle
        if exp - time.time() < 60:
            if refresh_access_token():
                return session.get('jwt_token')
    except:
        # Si le token est invalide, essaie de le renouveler
        if refresh_access_token():
            return session.get('jwt_token')
        return None
    
    return access_token

def check_microservices_status():
    """Vérifie l'état des microservices via le Gateway"""
    status = {
        'auth': False,
        'user': False,
        'orders': False,
        'gateway': False
    }
    
    # Vérifie d'abord le Gateway
    try:
        r = requests.get(f"{GATEWAY_URL}/health", timeout=2)
        if r.status_code == 200:
            status['gateway'] = True
            # Le Gateway peut retourner l'état des autres services
            data = r.json()
            if 'services' in data:
                services_status = data['services']
                status['auth'] = services_status.get('auth_service') == 'healthy'
                status['user'] = services_status.get('user_service') == 'healthy'
                status['orders'] = services_status.get('orders_service') == 'healthy'
    except:
        pass
    
    # Fallback: vérification directe si le Gateway ne retourne pas les infos
    if not status['gateway']:
        try:
            r = requests.get(f"{AUTH_SERVICE_URL}/health", timeout=1)
            status['auth'] = r.status_code == 200
        except:
            pass
        
        try:
            r = requests.get(f"{USER_SERVICE_URL}/health", timeout=1)
            status['user'] = r.status_code == 200
        except:
            pass
        
        try:
            r = requests.get(f"{ORDERS_SERVICE_URL}/health", timeout=1)
            status['orders'] = r.status_code == 200
        except:
            pass
    
    return status

# ========== FONCTIONS UTILITAIRES ==========

def est_connecte():
    return 'username' in session

def fetch_user(username):
    """Récupère un utilisateur depuis SQLite (fallback si microservice indisponible)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, email, role, created_at FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def authenticate_credentials(username, password):
    """Authentifie via Gateway (qui route vers Auth Service) ou fallback local"""
    # Essaie d'abord via Gateway
    try:
        response = requests.post(
            f"{GATEWAY_URL}/gateway/auth/login",
            json={"username": username, "password": password},
            timeout=2
        )
        if response.status_code == 200:
            data = response.json()
            # Stocke les tokens dans la session
            session['jwt_token'] = data['access_token']
            session['refresh_token'] = data.get('refresh_token')  # Stocke aussi le refresh token
            return {
                'id': data['user']['id'],
                'username': data['user']['username'],
                'email': data['user']['email'],
                'role': data['user']['role']
            }
    except:
        pass
    
    # Fallback: authentification locale
    user_row = fetch_user(username)
    if user_row and check_password_hash(user_row['password'], password):
        return {
            'id': user_row['id'],
            'username': user_row['username'],
            'email': user_row['email'],
            'role': user_row['role']
        }
    return None

def ajouter_historique(action, details=""):
    """Ajoute une action dans l'historique via Orders Service"""
    if not est_connecte():
        return
    
    token = get_user_token()
    username = session.get('username', 'Utilisateur Demo')
    user_id = session.get('user_id')
    
    # Essaie d'ajouter via Orders Service
    if token and user_id:
        try:
            call_orders_service('/orders', method='POST', data={
                'product_name': f'Action: {action}',
                'quantity': 1,
                'price': 0
            }, token=token)
        except:
            pass

# ========== ROUTES WEB ==========

@app.route('/')
def index():
    if not est_connecte():
        return redirect(url_for('login'))
    
    etat_circuit = breaker.current_state
    nb_echecs = breaker.fail_counter
    compteur = compteur_appels_banque
    
    return render_template('index.html', 
                          produit=PRODUIT,
                          etat_circuit=etat_circuit,
                          nb_echecs=nb_echecs,
                          compteur_appels=compteur)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if est_connecte():
            return redirect(url_for('index'))
        return render_template('login.html')

    username = (request.form.get('username') or '').strip()
    password = (request.form.get('password') or '').strip()

    if not username or not password:
        flash('Veuillez remplir tous les champs', 'danger')
        return render_template('login.html')

    user = authenticate_credentials(username, password)

    if user:
        session['username'] = user['username']
        session['role'] = user['role']
        session['user_id'] = user['id']
        flash(f'Bienvenue {username} !', 'success')
        return redirect(url_for('index'))

    flash('Identifiants incorrects', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Révoque le refresh token via Auth Service si disponible
    refresh_token = session.get('refresh_token')
    if refresh_token:
        try:
            requests.post(
                f"{GATEWAY_URL}/gateway/auth/logout",
                json={"refresh_token": refresh_token},
                timeout=2
            )
        except:
            pass
    
    session.clear()
    flash('Déconnexion réussie', 'info')
    return redirect(url_for('login'))


@app.route('/payer', methods=['POST'])
def payer():
    if not est_connecte():
        return redirect(url_for('index'))
    
    montant = PRODUIT['prix']
    ajouter_historique('Accès paiement', f'Montant: {montant}€')
    return redirect(url_for('banque', montant=montant))

@app.route('/banque')
def banque():
    if not est_connecte():
        return redirect(url_for('index'))
    
    montant = request.args.get('montant', PRODUIT['prix'])
    return render_template('banque.html', montant=montant)

@app.route('/traiter_paiement', methods=['POST'])
def traiter_paiement():
    if not est_connecte():
        return redirect(url_for('index'))
    
    montant = PRODUIT['prix']
    numero_carte = '1234 5678 9012 3456'
    
    try:
        resultat = breaker.call(lambda: banque_principale(montant, numero_carte))
        
        if resultat['success']:
            ajouter_historique('Paiement réussi', f"Transaction: {resultat['transaction_id']}")
            flash(f"Paiement accepté - Transaction: {resultat['transaction_id']}", 'success')
            flash(f"Traité par: {resultat['banque']}", 'success')
            return redirect(url_for('index'))
    except pybreaker.CircuitBreakerError:
        ajouter_historique('Paiement échoué', 'Circuit breaker ouvert')
        flash('ERREUR: Service bancaire indisponible', 'danger')
        return redirect(url_for('index'))
    except Exception as e:
        ajouter_historique('Paiement échoué', f'Erreur: {str(e)}')
        flash(f'ERREUR: {str(e)}', 'danger')
        return redirect(url_for('index'))

def banque_principale(montant, carte):
    global compteur_appels_banque
    compteur_appels_banque += 1
    if compteur_appels_banque <= 5:
        time.sleep(0.5)
        raise Exception("Erreur de connexion à la banque principale")
    time.sleep(0.3)
    return {
        'success': True,
        'transaction_id': f'BANK-PRIN-{compteur_appels_banque}-{random.randint(1000, 9999)}',
        'message': 'Paiement accepté par la banque principale',
        'montant': montant,
        'banque': 'Banque Principale'
    }

@app.route('/historique')
def historique():
    if not est_connecte():
        return redirect(url_for('login'))
    
    token = get_user_token()
    historique_data = []
    
    # Essaie de récupérer via Orders Service
    if token:
        orders_data = call_orders_service('/orders/history', token=token)
        if orders_data and 'history' in orders_data:
            historique_data = orders_data['history']
    
    return render_template('historique.html', 
                          historique=historique_data,
                          total=len(historique_data))

@app.route('/ajouter_utilisateur', methods=['GET', 'POST'])
def ajouter_utilisateur():
    if not est_connecte():
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')
        
        if not username or not password:
            flash('Le nom d\'utilisateur et le mot de passe sont obligatoires', 'danger')
            return render_template('ajouter_utilisateur.html')
        
        # Essaie d'abord via le User Service via Gateway
        token = get_user_token()
        if token:
            user_data = call_user_service('/users', method='POST', data={
                'username': username,
                'password': password,
                'email': email,
                'role': role
            }, token=token)
            
            if user_data and 'user' in user_data:
                flash(f'Utilisateur "{username}" créé avec succès !', 'success')
                return redirect(url_for('liste_utilisateurs'))
            elif user_data and 'message' in user_data:
                flash(user_data['message'], 'danger')
                return render_template('ajouter_utilisateur.html')
        
        # Fallback: création directe dans la base (si microservices indisponibles)
        try:
            conn = get_db()
            cursor = conn.cursor()
            hashed_password = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            ''', (username, hashed_password, email, role))
            conn.commit()
            conn.close()
            
            flash(f'Utilisateur "{username}" créé avec succès !', 'success')
            return redirect(url_for('liste_utilisateurs'))
        except sqlite3.IntegrityError:
            flash(f'Erreur: L\'utilisateur "{username}" existe déjà', 'danger')
        except Exception as e:
            flash(f'Erreur lors de la création: {str(e)}', 'danger')
    
    return render_template('ajouter_utilisateur.html')

@app.route('/liste_utilisateurs')
def liste_utilisateurs():
    if not est_connecte():
        return redirect(url_for('login'))
    
    # Essaie de récupérer via User Service
    token = get_user_token()
    users = []
    
    if token:
        users_data = call_user_service('/users', token=token)
        if users_data and 'users' in users_data:
            users = users_data['users']
    
    # Fallback: récupération locale
    if not users:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, email, role, created_at FROM users ORDER BY id')
        rows = cursor.fetchall()
        users = [dict(row) for row in rows]
        conn.close()
    
    return render_template('liste_utilisateurs.html', users=users)

@app.route('/api/users')
def api_users():
    """API endpoint pour récupérer tous les utilisateurs en JSON"""
    if not est_connecte():
        return jsonify({'error': 'Non authentifié'}), 401
    
    token = get_user_token()
    if token:
        # Essaie via Gateway
        data = call_user_service('/users', token=token)
        if data and 'users' in data:
            return jsonify(data), 200
    
    # Fallback: récupération directe depuis la base
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, role, created_at FROM users')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'users': users, 'total': len(users)}), 200

@app.route('/api/user')
def api_user():
    """API endpoint pour récupérer les infos de l'utilisateur connecté + historique en JSON"""
    if not est_connecte():
        return jsonify({'error': 'Non authentifié'}), 401
    
    user_id = session.get('user_id')
    username = session.get('username')
    role = session.get('role')
    
    # Récupère l'historique
    historique = []
    try:
        conn = sqlite3.connect('orders.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM historique WHERE user_id = ? ORDER BY timestamp DESC LIMIT 50', (user_id,))
        historique = [dict(row) for row in cursor.fetchall()]
        conn.close()
    except:
        pass
    
    return jsonify({
        'user': {
            'id': user_id,
            'username': username,
            'role': role
        },
        'historique': historique,
        'total_actions': len(historique)
    }), 200

@app.route('/supprimer_utilisateur/<int:user_id>', methods=['POST'])
def supprimer_utilisateur(user_id):
    if not est_connecte():
        return redirect(url_for('login'))
    
    current_user_id = session.get('user_id')
    if current_user_id == user_id:
        flash('Vous ne pouvez pas supprimer votre propre compte !', 'danger')
        return redirect(url_for('liste_utilisateurs'))
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            flash(f'Utilisateur "{user["username"]}" supprimé avec succès', 'success')
        conn.close()
    except Exception as e:
        flash(f'Erreur lors de la suppression: {str(e)}', 'danger')
    
    return redirect(url_for('liste_utilisateurs'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
