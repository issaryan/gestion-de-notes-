# backend/auth.py
import jwt  # Ajoutez cette ligne en haut
from datetime import datetime, timedelta
import logging
from datetime import datetime
from functools import wraps
from flask import session, abort
import bcrypt
from mysql.connector import IntegrityError, DatabaseError
from backend.database import db_connection
from backend.config import JWT_CONFIG

logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Exception personnalisée pour les erreurs d'authentification"""
    pass

def _hash_password(password: str) -> str:
    """Hash un mot de passe avec bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_hash: str, password: str) -> bool:
    """Vérifie un mot de passe contre son hash stocké"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
    except ValueError as e:
        logger.error(f"Erreur de vérification de mot de passe : {str(e)}")
        return False

def login_user(username: str, password: str) -> dict:
    """
    Authentifie un utilisateur et met à jour sa dernière connexion
    Retourne un token JWT et les informations utilisateur si réussi
    """
    try:
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT 
                    id, 
                    username, 
                    password_hash, 
                    role, 
                    nom, 
                    prenom,
                    email
                FROM users 
                WHERE username = %s
            ''', (username,))
            
            user = cursor.fetchone()
            if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                raise ValueError("Identifiants invalides")
            
            if not user or not verify_password(user['password_hash'], password):
                logger.warning(f"Tentative de connexion échouée pour {username}")
                raise AuthError("Identifiants invalides")

            # Mise à jour de la dernière connexion
            cursor.execute('''
                UPDATE users 
                SET last_login = NOW() 
                WHERE id = %s
            ''', (user['id'],))
            conn.commit()

            # Génération du token JWT
            token = jwt.encode({
                'sub': user['id'],
                'role': user['role'],
                'exp': datetime.utcnow() + timedelta(minutes=JWT_CONFIG['ACCESS_TOKEN_EXPIRE_MINUTES'])
            }, JWT_CONFIG['SECRET_KEY'], algorithm=JWT_CONFIG['ALGORITHM'])

            # Nettoyage des données sensibles et préparation de la réponse
            user.pop('password_hash', None)
            
            return {
                'token': token,
                'user': user
            }
            
    except DatabaseError as e:
        logger.error(f"Erreur base de données lors de la connexion : {str(e)}")
        raise AuthError("Erreur système temporaire") from e

def setup_session(user: dict):
    """Configure la session utilisateur"""
    session.clear()
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session.permanent = True

def logout_user():
    """Déconnecte l'utilisateur"""
    session.clear()

def get_current_user() -> dict:
    """Récupère les informations de l'utilisateur connecté"""
    if 'user_id' not in session:
        return None
        
    try:
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT 
                    id,
                    username,
                    role,
                    nom,
                    prenom,
                    email,
                    DATE_FORMAT(last_login, '%%d/%%m/%%Y %%H:%%i') as last_login
                FROM users 
                WHERE id = %s
            ''', (session['user_id'],))
            
            return cursor.fetchone()
            
    except DatabaseError as e:
        logger.error(f"Erreur de récupération utilisateur : {str(e)}")
        return None

def require_role(role: str):
    """Décorateur pour vérifier le rôle de l'utilisateur"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            current_user = get_current_user()
            if not current_user or current_user['role'] != role:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator

def register_user(user_data: dict) -> dict:
    """
    Enregistre un nouvel utilisateur avec validation
    Retourne l'utilisateur créé
    """
    required_fields = ['username', 'password', 'role']
    for field in required_fields:
        if not user_data.get(field):
            raise AuthError(f"Champ manquant: {field}")

    try:
        hashed_pw = _hash_password(user_data['password'])
        
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                INSERT INTO users (
                    username,
                    password_hash,
                    role,
                    nom,
                    prenom,
                    email
                ) VALUES (%s, %s, %s, %s, %s, %s)
            ''', (
                user_data['username'],
                hashed_pw,
                user_data['role'].lower(),
                user_data.get('nom'),
                user_data.get('prenom'),
                user_data.get('email')
            ))
            
            user_id = cursor.lastrowid
            conn.commit()
            
            return {
                'id': user_id,
                'username': user_data['username'],
                'role': user_data['role']
            }
            
    except IntegrityError as e:
        logger.error(f"Username déjà existant : {user_data['username']}")
        raise AuthError("Nom d'utilisateur déjà utilisé") from e
    except DatabaseError as e:
        logger.error(f"Erreur d'inscription : {str(e)}")
        raise AuthError("Erreur d'inscription") from e
