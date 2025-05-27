# backend/database.py
import mysql.connector
from contextlib import contextmanager
from typing import Optional, Dict, List
from backend.config import DB_CONFIG
import bcrypt
import logging

# Configuration du logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

@contextmanager
def db_connection():
    """Gestionnaire de contexte pour les connexions à la base de données"""
    conn = None
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        conn.autocommit = False  # Pour le contrôle manuel des transactions
        yield conn
    except mysql.connector.Error as e:
        logger.error(f"Database connection error: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """Initialisation de la base de données avec schéma corrigé"""
    with db_connection() as conn:
        cursor = conn.cursor()
        
        # Table des classes (version corrigée)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS classes (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL UNIQUE,
                level VARCHAR(50) NOT NULL,
                academic_year VARCHAR(20) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB
        ''')
        
        # Table des utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INT PRIMARY KEY AUTO_INCREMENT,
                username VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role ENUM('admin', 'teacher', 'student') NOT NULL,
                nom VARCHAR(255) NOT NULL,
                prenom VARCHAR(255) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                class_id INT,
                last_login DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_class_id (class_id),
                INDEX idx_role (role),
                FOREIGN KEY (class_id) 
                    REFERENCES classes(id) 
                    ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        ''')
        
        # Table des matières
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INT PRIMARY KEY AUTO_INCREMENT,
                name VARCHAR(255) NOT NULL,
                class_id INT NOT NULL,
                teacher_id INT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_subject (class_id, name),
                FOREIGN KEY (class_id) 
                    REFERENCES classes(id) 
                    ON DELETE CASCADE,
                FOREIGN KEY (teacher_id) 
                    REFERENCES users(id) 
                    ON DELETE CASCADE
            ) ENGINE=InnoDB
        ''')
        
        # Table des notes (nom de colonne corrigé)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grades (
                id INT PRIMARY KEY AUTO_INCREMENT,
                student_id INT NOT NULL,
                subject_id INT NOT NULL,
                grade DECIMAL(4,2) NOT NULL 
                    CHECK (grade BETWEEN 0 AND 20),
                evaluation_date DATE NOT NULL,
                comments TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_student (student_id),
                INDEX idx_subject (subject_id),
                FOREIGN KEY (student_id) 
                    REFERENCES users(id) 
                    ON DELETE CASCADE,
                FOREIGN KEY (subject_id) 
                    REFERENCES subjects(id) 
                    ON DELETE CASCADE
            ) ENGINE=InnoDB
        ''')
        
        # Table d'emploi du temps
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INT PRIMARY KEY AUTO_INCREMENT,
                subject_id INT NOT NULL,
                day ENUM('MON','TUE','WED','THU','FRI','SAT') NOT NULL,
                start_time TIME NOT NULL,
                end_time TIME NOT NULL,
                FOREIGN KEY (subject_id) 
                    REFERENCES subjects(id) 
                    ON DELETE CASCADE,
                INDEX idx_day (day)
            ) ENGINE=InnoDB
        ''')
        
        # Table d'audit
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_log (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT,
                action VARCHAR(50) NOT NULL,
                target_type VARCHAR(50),
                target_id INT,
                details TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) 
                    REFERENCES users(id) 
                    ON DELETE SET NULL
            ) ENGINE=InnoDB
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully")

def add_user(username: str, password: str, role: str, 
             nom: str, prenom: str, email: str, 
             class_id: Optional[int] = None) -> int:
    """Ajoute un utilisateur avec validation complète"""
    if role not in {'admin', 'teacher', 'student'}:
        raise ValueError("Role invalide")
    
    if role == 'student' and not class_id:
        raise ValueError("Les étudiants doivent avoir une classe")
    
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Validation de la classe si nécessaire
            if class_id:
                cursor.execute("SELECT id FROM classes WHERE id = %s", (class_id,))
                if not cursor.fetchone():
                    raise ValueError("Classe introuvable")
            
            cursor.execute('''
                INSERT INTO users 
                (username, password_hash, role, nom, prenom, email, class_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (username, password_hash, role, nom, prenom, email, class_id))
            
            # Audit
            cursor.execute('''
                INSERT INTO audit_log 
                (user_id, action, target_type, target_id)
                VALUES (%s, 'CREATE', 'USER', %s)
            ''', (cursor.lastrowid, cursor.lastrowid))
            
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.IntegrityError as e:
            conn.rollback()
            if 'Duplicate entry' in str(e):
                raise ValueError("Username ou email déjà existant")
            raise

def add_class(name: str, level: str, academic_year: str) -> int:
    """Crée une nouvelle classe avec validation"""
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO classes (name, level, academic_year)
                VALUES (%s, %s, %s)
            ''', (name, level, academic_year))
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.IntegrityError:
            conn.rollback()
            raise ValueError("Nom de classe déjà existant")

def add_subject(name: str, class_id: int, teacher_id: int) -> int:
    """Ajoute une matière avec validation des permissions"""
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Vérification que le professeur existe et a le bon rôle
            cursor.execute('''
                SELECT 1 FROM users 
                WHERE id = %s AND role = 'teacher'
            ''', (teacher_id,))
            if not cursor.fetchone():
                raise ValueError("Professeur invalide")
            
            # Vérification que la classe existe
            cursor.execute("SELECT 1 FROM classes WHERE id = %s", (class_id,))
            if not cursor.fetchone():
                raise ValueError("Classe invalide")
            
            cursor.execute('''
                INSERT INTO subjects (name, class_id, teacher_id)
                VALUES (%s, %s, %s)
            ''', (name, class_id, teacher_id))
            
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.IntegrityError:
            conn.rollback()
            raise ValueError("Matière déjà existante pour cette classe")

def add_grade(student_id: int, subject_id: int, 
              grade: float, date: str, comments: str = '') -> int:
    """Ajoute une note avec validation des contraintes"""
    if not (0 <= grade <= 20):
        raise ValueError("Note invalide (doit être entre 0 et 20)")
    
    with db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Vérification de l'existence de l'étudiant et de la matière
            cursor.execute('''
                SELECT 1 FROM users 
                WHERE id = %s AND role = 'student'
            ''', (student_id,))
            if not cursor.fetchone():
                raise ValueError("Étudiant introuvable")
            
            cursor.execute('''
                SELECT 1 FROM subjects WHERE id = %s
            ''', (subject_id,))
            if not cursor.fetchone():
                raise ValueError("Matière introuvable")
            
            cursor.execute('''
                INSERT INTO grades 
                (student_id, subject_id, grade, evaluation_date, comments)
                VALUES (%s, %s, %s, %s, %s)
            ''', (student_id, subject_id, grade, date, comments))
            
            conn.commit()
            return cursor.lastrowid
        except mysql.connector.Error as e:
            conn.rollback()
            raise ValueError(f"Erreur base de données: {e}")

def get_student_grades(student_id: int) -> List[Dict]:
    """Récupère toutes les notes d'un étudiant avec jointures optimisées"""
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT s.name as subject, g.grade, g.evaluation_date, g.comments,
                   c.name as class, CONCAT(u.prenom, ' ', u.nom) as teacher
            FROM grades g
            JOIN subjects s ON g.subject_id = s.id
            JOIN classes c ON s.class_id = c.id
            JOIN users u ON s.teacher_id = u.id
            WHERE g.student_id = %s
            ORDER BY g.evaluation_date DESC
        ''', (student_id,))
        return cursor.fetchall()

def get_class_students(class_id: int) -> List[Dict]:
    """Récupère tous les étudiants d'une classe avec statistiques"""
    with db_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('''
            SELECT u.id, u.nom, u.prenom, u.email,
                   COUNT(g.id) as nb_notes,
                   AVG(g.grade) as moyenne
            FROM users u
            LEFT JOIN grades g ON u.id = g.student_id
            WHERE u.class_id = %s AND u.role = 'student'
            GROUP BY u.id
            ORDER BY u.nom, u.prenom
        ''', (class_id,))
        return cursor.fetchall()

def log_audit_event(user_id: Optional[int], action: str, 
                    target_type: str = None, target_id: int = None, 
                    details: str = None):
    """Journalise une action dans l'audit log"""
    with db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO audit_log 
            (user_id, action, target_type, target_id, details)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, action, target_type, target_id, details))
        conn.commit()
