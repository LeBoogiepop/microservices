"""
Script pour initialiser la base de données users.db
"""
import sqlite3
import os
from werkzeug.security import generate_password_hash

DATABASE = 'users.db'

def init_db():
    """Initialise la base de données avec la table users"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Crée la table users si elle n'existe pas
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
    
    # Insère les utilisateurs par défaut s'ils n'existent pas
    default_users = [
        ('admin', 'admin123', 'admin@esme.fr', 'admin'),
        ('user1', 'password1', 'user1@esme.fr', 'user'),
        ('maxim', 'maxim', 'maxim@esme.fr', 'user')
    ]
    
    for username, password, email, role in default_users:
        try:
            # Hache le mot de passe avant insertion
            hashed_password = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, password, email, role)
                VALUES (?, ?, ?, ?)
            ''', (username, hashed_password, email, role))
            print(f"Utilisateur cree: {username}")
        except sqlite3.IntegrityError:
            # L'utilisateur existe déjà
            print(f"Utilisateur existe deja: {username}")
            pass
    
    conn.commit()
    conn.close()
    print(f"\nBase de donnees {DATABASE} initialisee avec succes!")

if __name__ == '__main__':
    init_db()

