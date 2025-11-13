"""
User Service - Service de gestion des utilisateurs
Port: 5002
Responsabilités:
- Gestion des profils utilisateurs
- CRUD utilisateurs
- Récupération des informations utilisateur
"""

from flask import Flask, request, jsonify
import sqlite3
import os
from werkzeug.security import generate_password_hash

app = Flask(__name__)

# Configuration de la base de données (partagée avec Auth Service)
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'users.db')

def get_db():
    """Connexion à la base de données SQLite avec timeout pour éviter les verrouillages"""
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def serialize_user(user_row, include_password=False):
    """Convertit une ligne SQLite en dictionnaire sérialisable."""
    if not user_row:
        return None

    user_dict = {
        'id': user_row['id'],
        'username': user_row['username'],
        'email': user_row['email'],
        'role': user_row['role'],
        'created_at': user_row['created_at']
    }

    if include_password:
        user_dict['password'] = user_row['password']

    return user_dict

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

def get_current_user_from_token():
    """Extrait l'utilisateur courant depuis le header X-User-Id (défini par le Gateway)."""
    user_id = request.headers.get('X-User-Id')
    if not user_id:
        return None
    try:
        return fetch_user_by_id(int(user_id))
    except (ValueError, TypeError):
        return None

# ========== ENDPOINTS ==========

@app.route('/users/profile', methods=['GET'])
def get_profile():
    """Récupère le profil de l'utilisateur connecté."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    profile_data = serialize_user(user_row)
    profile_data['email'] = profile_data.get('email') or f"{profile_data['username']}@example.com"
    profile_data['role'] = profile_data.get('role', 'user')

    return jsonify(profile_data), 200

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Récupère les informations d'un utilisateur par son ID."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    # Seul l'admin peut voir les autres utilisateurs, ou l'utilisateur peut voir son propre profil
    if user_row['role'] != 'admin' and user_row['id'] != user_id:
        return jsonify({'message': 'Accès refusé'}), 403

    target_user = fetch_user_by_id(user_id)
    if not target_user:
        return jsonify({'message': 'Utilisateur introuvable'}), 404

    return jsonify(serialize_user(target_user)), 200

@app.route('/users', methods=['GET'])
def list_users():
    """Liste tous les utilisateurs (admin uniquement)."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    if user_row['role'] != 'admin':
        return jsonify({'message': 'Accès refusé! Admin uniquement.'}), 403

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, email, role, created_at FROM users ORDER BY id')
    rows = cursor.fetchall()
    conn.close()

    users_list = [
        {
            'id': row['id'],
            'username': row['username'],
            'email': row['email'],
            'role': row['role'],
            'created_at': row['created_at']
        }
        for row in rows
    ]

    return jsonify({
        'users': users_list,
        'total': len(users_list),
        'database': 'SQLite (users.db)'
    }), 200

@app.route('/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Met à jour un utilisateur."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    # Seul l'admin peut modifier les autres utilisateurs, ou l'utilisateur peut modifier son propre profil
    if user_row['role'] != 'admin' and user_row['id'] != user_id:
        return jsonify({'message': 'Accès refusé'}), 403

    target_user = fetch_user_by_id(user_id)
    if not target_user:
        return jsonify({'message': 'Utilisateur introuvable'}), 404

    data = request.get_json(silent=True) or {}
    email = data.get('email', '').strip()
    role = data.get('role')

    # Seul l'admin peut changer les rôles
    if role and user_row['role'] != 'admin':
        return jsonify({'message': 'Seul un admin peut modifier les rôles'}), 403

    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if email:
            cursor.execute('UPDATE users SET email = ? WHERE id = ?', (email, user_id))
        if role and user_row['role'] == 'admin':
            cursor.execute('UPDATE users SET role = ? WHERE id = ?', (role, user_id))
        
        conn.commit()
        conn.close()

        updated_user = fetch_user_by_id(user_id)
        return jsonify({
            'message': 'Utilisateur mis à jour avec succès',
            'user': serialize_user(updated_user)
        }), 200

    except Exception as e:
        return jsonify({'message': f'Erreur lors de la mise à jour: {str(e)}'}), 500

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Supprime un utilisateur."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    if user_row['role'] != 'admin':
        return jsonify({'message': 'Accès refusé! Admin uniquement.'}), 403

    # Empêche la suppression de son propre compte
    if user_row['id'] == user_id:
        return jsonify({'message': 'Vous ne pouvez pas supprimer votre propre compte'}), 400

    target_user = fetch_user_by_id(user_id)
    if not target_user:
        return jsonify({'message': 'Utilisateur introuvable'}), 404

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

        return jsonify({
            'message': f'Utilisateur "{target_user["username"]}" supprimé avec succès'
        }), 200

    except Exception as e:
        return jsonify({'message': f'Erreur lors de la suppression: {str(e)}'}), 500

@app.route('/users/by-username/<username>', methods=['GET'])
def get_user_by_username(username):
    """Récupère un utilisateur par son nom d'utilisateur."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    target_user = fetch_user(username)
    if not target_user:
        return jsonify({'message': 'Utilisateur introuvable'}), 404

    # Seul l'admin peut voir les autres utilisateurs, ou l'utilisateur peut voir son propre profil
    if user_row['role'] != 'admin' and user_row['id'] != target_user['id']:
        return jsonify({'message': 'Accès refusé'}), 403

    return jsonify(serialize_user(target_user)), 200

@app.route('/users', methods=['POST'])
def create_user():
    """Crée un nouvel utilisateur (admin uniquement)."""
    user_row = get_current_user_from_token()
    if not user_row:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    if user_row['role'] != 'admin':
        return jsonify({'message': 'Accès refusé! Admin uniquement.'}), 403

    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '').strip()
    email = (data.get('email') or '').strip()
    role = data.get('role', 'user')

    if not username or not password:
        return jsonify({'message': 'Le nom d\'utilisateur et le mot de passe sont obligatoires'}), 400

    # Vérifie si l'utilisateur existe déjà
    existing_user = fetch_user(username)
    if existing_user:
        return jsonify({'message': f'L\'utilisateur "{username}" existe déjà'}), 400

    try:
        from werkzeug.security import generate_password_hash
        from datetime import datetime
        
        conn = get_db()
        cursor = conn.cursor()
        hashed_password = generate_password_hash(password)
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute('''
            INSERT INTO users (username, password, email, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, hashed_password, email, role, created_at))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()

        # Récupère l'utilisateur créé
        new_user = fetch_user_by_id(user_id)
        return jsonify({
            'message': f'Utilisateur "{username}" créé avec succès',
            'user': serialize_user(new_user)
        }), 201

    except Exception as e:
        return jsonify({'message': f'Erreur lors de la création: {str(e)}'}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé pour vérifier que le service fonctionne."""
    return jsonify({
        'status': 'healthy',
        'service': 'user_service',
        'port': 5002
    }), 200

if __name__ == '__main__':
    print("Demarrage du User Service sur le port 5002...")
    app.run(debug=True, port=5002, host='0.0.0.0')

