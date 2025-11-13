"""
API Gateway - Point d'entrée unique pour tous les clients
Port: 5000
Responsabilités:
- Valider les tokens JWT avant de router
- Router les requêtes vers les bons services
- Gérer les erreurs et les timeouts
"""

from flask import Flask, request, jsonify
import requests
from functools import wraps
import os

app = Flask(__name__)

# Configuration des services
AUTH_SERVICE_URL = os.getenv('AUTH_SERVICE_URL', 'http://localhost:5001')
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:5002')
ORDERS_SERVICE_URL = os.getenv('ORDERS_SERVICE_URL', 'http://localhost:5003')

# Timeout pour les requêtes vers les services (en secondes)
SERVICE_TIMEOUT = 5

def verify_token_with_auth_service(token):
    """Vérifie un token JWT en appelant l'Auth Service."""
    try:
        response = requests.post(
            f'{AUTH_SERVICE_URL}/auth/verify',
            json={'token': token},
            timeout=SERVICE_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('valid', False), data.get('user')
        return False, None
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de la vérification du token: {e}")
        return False, None

def gateway_auth_required(f):
    """Décorateur pour protéger une route avec validation JWT via Auth Service."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == 'bearer':
                token = parts[1]
            else:
                return jsonify({'message': 'Format de token invalide. Utiliser "Bearer <token>"'}), 401

        if not token:
            return jsonify({'message': 'Token manquant'}), 401

        # Vérifie le token via l'Auth Service
        is_valid, user = verify_token_with_auth_service(token)
        if not is_valid or not user:
            return jsonify({'message': 'Token invalide ou expiré'}), 401

        # Ajoute les informations utilisateur aux headers pour les services en aval
        request.environ['X-User-Id'] = str(user['id'])
        request.environ['X-Username'] = user['username']
        request.environ['X-User-Role'] = user.get('role', 'user')

        return f(user, *args, **kwargs)

    return decorated

def forward_request(service_url, path, method='GET', user=None):
    """Forward une requête vers un service backend."""
    url = f'{service_url}{path}'
    
    # Prépare les headers
    headers = {}
    if user:
        headers['X-User-Id'] = str(user['id'])
        headers['X-Username'] = user['username']
        headers['X-User-Role'] = user.get('role', 'user')
    
    # Copie les headers de la requête originale (sauf Authorization)
    for key, value in request.headers:
        if key.lower() not in ['authorization', 'host', 'content-length']:
            headers[key] = value

    try:
        # Forward la requête
        if method == 'GET':
            response = requests.get(url, headers=headers, params=request.args, timeout=SERVICE_TIMEOUT)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=request.get_json(silent=True), timeout=SERVICE_TIMEOUT)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=request.get_json(silent=True), timeout=SERVICE_TIMEOUT)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=SERVICE_TIMEOUT)
        else:
            return jsonify({'message': f'Méthode {method} non supportée'}), 405

        # Retourne la réponse du service
        try:
            return jsonify(response.json()), response.status_code
        except ValueError:
            return response.text, response.status_code

    except requests.exceptions.Timeout:
        return jsonify({'message': 'Service temporairement indisponible (timeout)'}), 503
    except requests.exceptions.ConnectionError:
        return jsonify({'message': 'Service indisponible (connexion impossible)'}), 503
    except requests.exceptions.RequestException as e:
        return jsonify({'message': f'Erreur lors de la communication avec le service: {str(e)}'}), 500

# ========== ROUTES AUTH (sans authentification) ==========

@app.route('/gateway/auth/login', methods=['POST'])
def route_auth_login():
    """Route les requêtes de login vers l'Auth Service."""
    return forward_request(AUTH_SERVICE_URL, '/auth/login', method='POST')

@app.route('/gateway/auth/refresh', methods=['POST'])
def route_auth_refresh():
    """Route les requêtes de refresh vers l'Auth Service."""
    return forward_request(AUTH_SERVICE_URL, '/auth/refresh', method='POST')

@app.route('/gateway/auth/logout', methods=['POST'])
def route_auth_logout():
    """Route les requêtes de logout vers l'Auth Service."""
    return forward_request(AUTH_SERVICE_URL, '/auth/logout', method='POST')

# ========== ROUTES USERS (avec authentification) ==========

@app.route('/gateway/users/profile', methods=['GET'])
@gateway_auth_required
def route_users_profile(current_user):
    """Route les requêtes de profil vers le User Service."""
    return forward_request(USER_SERVICE_URL, '/users/profile', method='GET', user=current_user)

@app.route('/gateway/users', methods=['GET', 'POST'])
@gateway_auth_required
def route_users_list(current_user):
    """Route les requêtes de liste et création d'utilisateurs vers le User Service."""
    method = request.method
    return forward_request(USER_SERVICE_URL, '/users', method=method, user=current_user)

@app.route('/gateway/users/<int:user_id>', methods=['GET', 'PUT', 'DELETE'])
@gateway_auth_required
def route_users_by_id(current_user, user_id):
    """Route les requêtes utilisateur par ID vers le User Service."""
    method = request.method
    return forward_request(USER_SERVICE_URL, f'/users/{user_id}', method=method, user=current_user)

@app.route('/gateway/users/by-username/<username>', methods=['GET'])
@gateway_auth_required
def route_users_by_username(current_user, username):
    """Route les requêtes utilisateur par username vers le User Service."""
    return forward_request(USER_SERVICE_URL, f'/users/by-username/{username}', method='GET', user=current_user)

# ========== ROUTES ORDERS (avec authentification) ==========

@app.route('/gateway/orders', methods=['GET', 'POST'])
@gateway_auth_required
def route_orders(current_user):
    """Route les requêtes de commandes vers le Orders Service."""
    method = request.method
    return forward_request(ORDERS_SERVICE_URL, '/orders', method=method, user=current_user)

@app.route('/gateway/orders/<int:order_id>', methods=['GET', 'PUT'])
@gateway_auth_required
def route_orders_by_id(current_user, order_id):
    """Route les requêtes de commande par ID vers le Orders Service."""
    method = request.method
    return forward_request(ORDERS_SERVICE_URL, f'/orders/{order_id}', method=method, user=current_user)

@app.route('/gateway/orders/history', methods=['GET'])
@gateway_auth_required
def route_orders_history(current_user):
    """Route les requêtes d'historique vers le Orders Service."""
    return forward_request(ORDERS_SERVICE_URL, '/orders/history', method='GET', user=current_user)

@app.route('/gateway/orders/stats', methods=['GET'])
@gateway_auth_required
def route_orders_stats(current_user):
    """Route les requêtes de statistiques vers le Orders Service."""
    return forward_request(ORDERS_SERVICE_URL, '/orders/stats', method='GET', user=current_user)

# ========== ROUTES DE SANTÉ ==========

@app.route('/health', methods=['GET'])
def gateway_health():
    """Vérifie la santé du Gateway."""
    # Retourne simplement que le Gateway est en vie
    # La vérification des autres services peut être faite séparément
    return jsonify({
        'status': 'healthy',
        'service': 'api_gateway',
        'port': 5004
    }), 200

@app.route('/', methods=['GET'])
def index():
    """Page d'accueil du Gateway."""
    return jsonify({
        'message': 'API Gateway - Architecture Microservices',
        'version': '1.0.0',
        'port': 5004,
        'note': 'Gateway sur port 5004 (app.py utilise port 5000)',
        'endpoints': {
            'auth': {
                'login': 'POST /gateway/auth/login',
                'refresh': 'POST /gateway/auth/refresh',
                'logout': 'POST /gateway/auth/logout'
            },
            'users': {
                'profile': 'GET /gateway/users/profile',
                'list': 'GET /gateway/users',
                'get_by_id': 'GET /gateway/users/<id>',
                'update': 'PUT /gateway/users/<id>',
                'delete': 'DELETE /gateway/users/<id>'
            },
            'orders': {
                'list': 'GET /gateway/orders',
                'create': 'POST /gateway/orders',
                'get_by_id': 'GET /gateway/orders/<id>',
                'update': 'PUT /gateway/orders/<id>',
                'history': 'GET /gateway/orders/history',
                'stats': 'GET /gateway/orders/stats'
            },
            'health': 'GET /health'
        }
    }), 200

if __name__ == '__main__':
    print("Demarrage de l'API Gateway sur le port 5004...")
    print(f"   Auth Service: {AUTH_SERVICE_URL}")
    print(f"   User Service: {USER_SERVICE_URL}")
    print(f"   Orders Service: {ORDERS_SERVICE_URL}")
    app.run(debug=True, port=5004, host='0.0.0.0')

