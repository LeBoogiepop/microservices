"""
Auth Service - Service d'authentification JWT
Port: 5001
Responsabilités:
- Générer les tokens JWT (access + refresh)
- Vérifier la validité des tokens
- Gérer les refresh tokens
- Authentifier les utilisateurs
"""

from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import sqlite3
import secrets
import jwt
from werkzeug.security import check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'votre-cle-secrete-ici')

# Configuration de la base de données (partagée avec User Service)
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.db')

def get_db():
    """Connexion à la base de données SQLite avec timeout pour éviter les verrouillages"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def fetch_user(username):
    """Récupère un utilisateur depuis SQLite."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, email, role, created_at FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def fetch_user_by_id(user_id):
    """Récupère un utilisateur par son ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, password, email, role, created_at FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def authenticate_credentials(username, password):
    """Vérifie les identifiants et retourne l'utilisateur si valide."""
    user_row = fetch_user(username)
    if user_row and check_password_hash(user_row['password'], password):
        return user_row
    return None

def generate_jwt_token(username, expires_delta=timedelta(minutes=15), token_type='access', jti=None):
    """Génère un token JWT pour l'utilisateur fourni."""
    expiration = datetime.utcnow() + expires_delta
    payload = {
        'username': username,
        'type': token_type,
        'exp': expiration
    }

    if jti:
        payload['jti'] = jti

    token = jwt.encode(
        payload,
        app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    # PyJWT peut renvoyer des bytes selon la version
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token, expiration

def store_refresh_token(user_id, jti, expires_at):
    """Stocke un refresh token dans la base de données."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO refresh_tokens (jti, user_id, created_at, expires_at, revoked)
        VALUES (?, ?, ?, ?, 0)
    ''', (jti, user_id, datetime.utcnow().isoformat(), expires_at.isoformat()))
    conn.commit()
    conn.close()

def mark_refresh_token_revoked(jti):
    """Marque un refresh token comme révoqué."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE refresh_tokens SET revoked = 1 WHERE jti = ?', (jti,))
    conn.commit()
    conn.close()

def is_refresh_token_revoked_or_expired(jti):
    """Vérifie si un refresh token est révoqué ou expiré."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT jti, user_id, revoked, expires_at FROM refresh_tokens WHERE jti = ?', (jti,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return True, None

    revoked, expires_at = row['revoked'], row['expires_at']
    if revoked:
        return True, row

    try:
        expires = datetime.fromisoformat(expires_at)
    except ValueError:
        return True, row

    return expires <= datetime.utcnow(), row

def create_token_pair(user_row):
    """Crée une paire de tokens (access + refresh)."""
    username = user_row['username']
    user_id = user_row['id']

    access_token, access_exp = generate_jwt_token(username, expires_delta=timedelta(minutes=15), token_type='access')

    refresh_jti = secrets.token_hex(16)
    refresh_token, refresh_exp = generate_jwt_token(
        username,
        expires_delta=timedelta(days=7),
        token_type='refresh',
        jti=refresh_jti
    )

    store_refresh_token(user_id, refresh_jti, refresh_exp)

    return {
        'access_token': access_token,
        'access_expires_at': access_exp,
        'refresh_token': refresh_token,
        'refresh_expires_at': refresh_exp
    }

# ========== ENDPOINTS ==========

@app.route('/auth/login', methods=['POST'])
def login():
    """Endpoint pour authentifier un utilisateur et générer des tokens JWT."""
    auth = request.get_json(silent=True) or {}
    username = (auth.get('username') or '').strip()
    password = (auth.get('password') or '').strip()

    if not username or not password:
        return jsonify({'message': 'Données manquantes (username, password)'}), 400

    user_row = authenticate_credentials(username, password)
    if not user_row:
        return jsonify({'message': 'Identifiants incorrects'}), 401

    tokens = create_token_pair(user_row)
    return jsonify({
        'access_token': tokens['access_token'],
        'access_expires_at': tokens['access_expires_at'].isoformat() + 'Z',
        'refresh_token': tokens['refresh_token'],
        'refresh_expires_at': tokens['refresh_expires_at'].isoformat() + 'Z',
        'user': {
            'id': user_row['id'],
            'username': user_row['username'],
            'email': user_row['email'],
            'role': user_row['role']
        },
        'message': f'Connexion réussie ! Bienvenue {username}'
    }), 200

@app.route('/auth/verify', methods=['POST'])
def verify_token():
    """Endpoint pour vérifier la validité d'un token JWT."""
    data = request.get_json(silent=True) or {}
    token = (data.get('token') or '').strip()

    if not token:
        return jsonify({'message': 'Token manquant'}), 400

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        username = payload.get('username')
        token_type = payload.get('type')

        if not username:
            return jsonify({'valid': False, 'message': 'Token invalide (pas de username)'}), 200

        if token_type != 'access':
            return jsonify({'valid': False, 'message': 'Token invalide (type)'}), 200

        # Vérifie que l'utilisateur existe toujours
        user_row = fetch_user(username)
        if not user_row:
            return jsonify({'valid': False, 'message': 'Utilisateur inexistant'}), 200

        return jsonify({
            'valid': True,
            'user': {
                'id': user_row['id'],
                'username': user_row['username'],
                'email': user_row['email'],
                'role': user_row['role']
            },
            'payload': payload
        }), 200

    except jwt.ExpiredSignatureError:
        return jsonify({'valid': False, 'message': 'Token expiré'}), 200
    except jwt.InvalidTokenError as e:
        return jsonify({'valid': False, 'message': f'Token invalide: {str(e)}'}), 200

@app.route('/auth/refresh', methods=['POST'])
def refresh_token():
    """Endpoint pour renouveler les tokens avec un refresh token."""
    data = request.get_json(silent=True) or {}
    raw_refresh = (data.get('refresh_token') or '').strip()

    if not raw_refresh:
        return jsonify({'message': 'Refresh token manquant'}), 400

    try:
        payload = jwt.decode(raw_refresh, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        try:
            payload = jwt.decode(
                raw_refresh,
                app.config['SECRET_KEY'],
                algorithms=['HS256'],
                options={'verify_exp': False}
            )
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Refresh token invalide'}), 401
        return jsonify({'message': 'Refresh token expiré, veuillez vous reconnecter'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Refresh token invalide'}), 401

    if payload.get('type') != 'refresh':
        return jsonify({'message': 'Token invalide (type)'}), 401

    jti = payload.get('jti')
    if not jti:
        return jsonify({'message': 'Refresh token sans identifiant'}), 401

    revoked_or_expired, row = is_refresh_token_revoked_or_expired(jti)
    if revoked_or_expired or not row:
        return jsonify({'message': 'Refresh token révoqué ou expiré'}), 401

    user_row = fetch_user_by_id(row['user_id'])
    if not user_row:
        mark_refresh_token_revoked(jti)
        return jsonify({'message': 'Utilisateur introuvable'}), 401

    # Rotation : révoque l'ancien refresh token et renvoie une nouvelle paire
    mark_refresh_token_revoked(jti)
    tokens = create_token_pair(user_row)

    return jsonify({
        'access_token': tokens['access_token'],
        'access_expires_at': tokens['access_expires_at'].isoformat() + 'Z',
        'refresh_token': tokens['refresh_token'],
        'refresh_expires_at': tokens['refresh_expires_at'].isoformat() + 'Z',
        'message': 'Tokens renouvelés avec succès'
    }), 200

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Endpoint pour révoquer un refresh token (déconnexion)."""
    data = request.get_json(silent=True) or {}
    raw_refresh = (data.get('refresh_token') or '').strip()

    if not raw_refresh:
        return jsonify({'message': 'Refresh token manquant'}), 400

    try:
        payload = jwt.decode(raw_refresh, app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        try:
            payload = jwt.decode(
                raw_refresh,
                app.config['SECRET_KEY'],
                algorithms=['HS256'],
                options={'verify_exp': False}
            )
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token invalide'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Token invalide'}), 401

    if payload.get('type') != 'refresh':
        return jsonify({'message': 'Token invalide (type)'}), 401

    jti = payload.get('jti')
    if not jti:
        return jsonify({'message': 'Refresh token sans identifiant'}), 401

    mark_refresh_token_revoked(jti)
    return jsonify({'message': 'Déconnexion réussie'}), 200

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé pour vérifier que le service fonctionne."""
    return jsonify({
        'status': 'healthy',
        'service': 'auth_service',
        'port': 5001
    }), 200

if __name__ == '__main__':
    print("Demarrage de l'Auth Service sur le port 5001...")
    app.run(debug=True, port=5001, host='0.0.0.0')

