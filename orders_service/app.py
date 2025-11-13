"""
Orders Service - Service de gestion des commandes
Port: 5003
Responsabilités:
- Gestion des commandes
- Historique des commandes
- API métier protégée
"""

from flask import Flask, request, jsonify
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)

# Configuration de la base de données
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'orders.db')

def get_db():
    """Connexion à la base de données SQLite pour les commandes"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données avec les tables nécessaires"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Table des commandes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER DEFAULT 1,
            price REAL NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # Table de l'historique des actions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialise la base de données au démarrage
init_db()

def get_current_user_from_token():
    """Extrait l'utilisateur courant depuis le header X-User-Id (défini par le Gateway)."""
    user_id = request.headers.get('X-User-Id')
    username = request.headers.get('X-Username')
    if not user_id:
        return None, None
    try:
        return int(user_id), username
    except (ValueError, TypeError):
        return None, None

def add_history(user_id, username, action, details=""):
    """Ajoute une entrée dans l'historique."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO history (user_id, username, action, details, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, username, action, details, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()

# ========== ENDPOINTS ==========

@app.route('/orders', methods=['GET'])
def list_orders():
    """Liste les commandes de l'utilisateur connecté."""
    user_id, username = get_current_user_from_token()
    if not user_id:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, product_name, quantity, price, total, status, created_at
        FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()

    orders = [
        {
            'id': row['id'],
            'user_id': row['user_id'],
            'product_name': row['product_name'],
            'quantity': row['quantity'],
            'price': row['price'],
            'total': row['total'],
            'status': row['status'],
            'created_at': row['created_at']
        }
        for row in rows
    ]

    return jsonify({
        'orders': orders,
        'total': len(orders)
    }), 200

@app.route('/orders', methods=['POST'])
def create_order():
    """Crée une nouvelle commande."""
    user_id, username = get_current_user_from_token()
    if not user_id:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    data = request.get_json(silent=True) or {}
    product_name = data.get('product_name', '').strip()
    quantity = data.get('quantity', 1)
    price = data.get('price', 0)

    if not product_name or price <= 0:
        return jsonify({'message': 'Données invalides (product_name et price requis)'}), 400

    try:
        quantity = int(quantity)
        price = float(price)
        total = quantity * price
    except (ValueError, TypeError):
        return jsonify({'message': 'Données invalides (quantity et price doivent être numériques)'}), 400

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (user_id, product_name, quantity, price, total, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        ''', (user_id, product_name, quantity, price, total))
        order_id = cursor.lastrowid
        conn.commit()
        conn.close()

        add_history(user_id, username or 'unknown', 'Commande créée', f'Commande #{order_id}: {product_name} x{quantity} = {total}€')

        return jsonify({
            'message': 'Commande créée avec succès',
            'order': {
                'id': order_id,
                'user_id': user_id,
                'product_name': product_name,
                'quantity': quantity,
                'price': price,
                'total': total,
                'status': 'pending'
            }
        }), 201

    except Exception as e:
        return jsonify({'message': f'Erreur lors de la création de la commande: {str(e)}'}), 500

@app.route('/orders/<int:order_id>', methods=['GET'])
def get_order(order_id):
    """Récupère les détails d'une commande."""
    user_id, username = get_current_user_from_token()
    if not user_id:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, product_name, quantity, price, total, status, created_at
        FROM orders
        WHERE id = ? AND user_id = ?
    ''', (order_id, user_id))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({'message': 'Commande introuvable'}), 404

    order = {
        'id': row['id'],
        'user_id': row['user_id'],
        'product_name': row['product_name'],
        'quantity': row['quantity'],
        'price': row['price'],
        'total': row['total'],
        'status': row['status'],
        'created_at': row['created_at']
    }

    return jsonify(order), 200

@app.route('/orders/<int:order_id>', methods=['PUT'])
def update_order_status(order_id):
    """Met à jour le statut d'une commande."""
    user_id, username = get_current_user_from_token()
    if not user_id:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    data = request.get_json(silent=True) or {}
    status = data.get('status', '').strip()

    if not status:
        return jsonify({'message': 'Statut requis'}), 400

    valid_statuses = ['pending', 'processing', 'shipped', 'delivered', 'cancelled']
    if status not in valid_statuses:
        return jsonify({'message': f'Statut invalide. Valeurs acceptées: {", ".join(valid_statuses)}'}), 400

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()

    if not order:
        conn.close()
        return jsonify({'message': 'Commande introuvable'}), 404

    # Seul le propriétaire peut modifier sa commande
    if order['user_id'] != user_id:
        conn.close()
        return jsonify({'message': 'Accès refusé'}), 403

    cursor.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

    add_history(user_id, username or 'unknown', 'Statut commande modifié', f'Commande #{order_id}: {status}')

    return jsonify({
        'message': 'Statut de la commande mis à jour',
        'order_id': order_id,
        'status': status
    }), 200

@app.route('/orders/history', methods=['GET'])
def get_history():
    """Récupère l'historique des actions de l'utilisateur connecté."""
    user_id, username = get_current_user_from_token()
    if not user_id:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, user_id, username, action, details, timestamp
        FROM history
        WHERE user_id = ?
        ORDER BY timestamp DESC
        LIMIT 100
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()

    history = [
        {
            'id': row['id'],
            'user_id': row['user_id'],
            'username': row['username'],
            'action': row['action'],
            'details': row['details'],
            'timestamp': row['timestamp']
        }
        for row in rows
    ]

    return jsonify({
        'history': history,
        'total': len(history)
    }), 200

@app.route('/orders/stats', methods=['GET'])
def get_stats():
    """Récupère les statistiques de l'utilisateur connecté."""
    user_id, username = get_current_user_from_token()
    if not user_id:
        return jsonify({'message': 'Utilisateur non authentifié'}), 401

    conn = get_db()
    cursor = conn.cursor()
    
    # Nombre total de commandes
    cursor.execute('SELECT COUNT(*) as total FROM orders WHERE user_id = ?', (user_id,))
    total_orders = cursor.fetchone()['total']
    
    # Montant total dépensé
    cursor.execute('SELECT SUM(total) as total_spent FROM orders WHERE user_id = ?', (user_id,))
    total_spent = cursor.fetchone()['total_spent'] or 0
    
    # Commandes par statut
    cursor.execute('''
        SELECT status, COUNT(*) as count
        FROM orders
        WHERE user_id = ?
        GROUP BY status
    ''', (user_id,))
    status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
    
    conn.close()

    return jsonify({
        'user_id': user_id,
        'total_orders': total_orders,
        'total_spent': float(total_spent),
        'orders_by_status': status_counts
    }), 200

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé pour vérifier que le service fonctionne."""
    return jsonify({
        'status': 'healthy',
        'service': 'orders_service',
        'port': 5003
    }), 200

if __name__ == '__main__':
    print("Demarrage du Orders Service sur le port 5003...")
    app.run(debug=True, port=5003, host='0.0.0.0')

