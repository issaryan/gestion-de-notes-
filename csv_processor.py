# csv_processor.py
import csv
import io
import mysql.connector
import bcrypt
from datetime import datetime
from backend.database import db_connection
from backend.config import DB_CONFIG

CSV_CONFIG = {
    'user_required_fields': ['username', 'password', 'role', 'nom', 'prenom', 'email'],
    'class_required_fields': ['name', 'level', 'academic_year'],
    'grade_required_fields': ['student_email', 'subject_name', 'grade', 'comments'],
    'max_grade': 20,
    'min_grade': 0
}

def process_csv(csv_data, actor_role=None):

    if not re.match(r'^student_id,subject_id,grade(\n\d+,\d+,\d+(\.\d+)?)+$', content):
        raise ValueError("Format CSV invalide")

    """Gère l'importation de données massives pour les administrateurs"""
    try:
        # Détection du type de CSV
        reader = csv.DictReader(io.StringIO(csv_data))
        fieldnames = [fn.lower().strip() for fn in reader.fieldnames] if reader.fieldnames else []
        
        if all(field in fieldnames for field in CSV_CONFIG['user_required_fields']):
            return _process_user_csv(reader)
        elif all(field in fieldnames for field in CSV_CONFIG['class_required_fields']):
            return _process_class_csv(reader)
        else:
            return {
                'success': False,
                'message': f"Format CSV non reconnu. Colonnes détectées: {fieldnames}",
                'processed': 0
            }

    except Exception as e:
        return {
            'success': False,
            'message': f"Erreur de traitement : {str(e)}",
            'processed': 0
        }

def process_grades_csv(csv_data, teacher_id):
    """Gère l'importation de notes par les enseignants"""
    try:
        with db_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            reader = csv.DictReader(io.StringIO(csv_data))
            if not reader.fieldnames:
                raise ValueError("Fichier CSV vide ou mal formaté")
                
            fieldnames = [fn.lower().strip() for fn in reader.fieldnames]
            
            # Validation des en-têtes
            missing_fields = [field for field in CSV_CONFIG['grade_required_fields'] if field not in fieldnames]
            if missing_fields:
                raise ValueError(f"En-têtes CSV manquants: {missing_fields}")

            grades_to_insert = []
            errors = []
            
            for idx, row in enumerate(reader, start=2):  # Ligne 1 = en-têtes
                try:
                    # Nettoyage des données
                    row = {k.lower().strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                    
                    # Validation de la note
                    try:
                        grade = float(row['grade'])
                    except ValueError:
                        raise ValueError("Note doit être un nombre")
                        
                    if not CSV_CONFIG['min_grade'] <= grade <= CSV_CONFIG['max_grade']:
                        raise ValueError(f"Note invalide ({CSV_CONFIG['min_grade']}-{CSV_CONFIG['max_grade']})")

                    # Récupération ID étudiant
                    cursor.execute(
                        "SELECT id FROM users WHERE email = %s AND role = 'student'",
                        (row['student_email'].lower(),)
                    )
                    student = cursor.fetchone()
                    if not student:
                        raise ValueError("Étudiant non trouvé")

                    # Vérification association matière/enseignant
                    cursor.execute(
                        """SELECT s.id 
                        FROM subjects s
                        WHERE s.name = %s AND s.teacher_id = %s""",
                        (row['subject_name'].strip(), teacher_id)
                    )
                    subject = cursor.fetchone()
                    if not subject:
                        raise ValueError("Matière non attribuée à l'enseignant")

                    grades_to_insert.append((
                        student['id'],
                        subject['id'],
                        grade,
                        row['comments'][:255] if row['comments'] else '',  # Troncature des commentaires
                        datetime.now().date()
                    ))

                except Exception as e:
                    errors.append({
                        'ligne': idx,
                        'erreur': str(e),
                        'donnees': dict(row)
                    })

            # Insertion en masse si aucune erreur critique
            if errors and len(errors) == len(list(csv.DictReader(io.StringIO(csv_data)))):
                return {
                    'success': False,
                    'message': f"Toutes les lignes contiennent des erreurs",
                    'errors': errors,
                    'inserted': 0
                }

            if grades_to_insert:
                cursor.executemany(
                    """INSERT INTO grades 
                    (student_id, subject_id, grade, comments, evaluation_date)
                    VALUES (%s, %s, %s, %s, %s)""",
                    grades_to_insert
                )
                conn.commit()

            return {
                'success': len(errors) == 0,
                'inserted': len(grades_to_insert),
                'errors': errors,
                'message': f"{len(grades_to_insert)} notes importées avec succès" + 
                          (f", {len(errors)} erreurs" if errors else "")
            }

    except Exception as e:
        return {
            'success': False,
            'message': f"Erreur de traitement : {str(e)}",
            'inserted': 0,
            'errors': []
        }

def _process_user_csv(reader):
    if row['role'].lower() == 'student' and not row.get('class_id'):
        raise ValueError("Les étudiants doivent avoir une classe")
    cursor.execute("SELECT id FROM classes WHERE id = %s", (row['class_id'],))
    if not cursor.fetchone():
        raise ValueError(f"Classe {row['class_id']} introuvable")
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            
            inserted = 0
            errors = []
            
            for idx, row in enumerate(reader, start=2):
                try:
                    # Nettoyage des données
                    row = {k.lower().strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                    
                    # Validation des données
                    required_fields = ['username', 'password', 'role', 'nom', 'prenom', 'email']
                    missing_fields = [field for field in required_fields if not row.get(field)]
                    if missing_fields:
                        raise ValueError(f"Champs manquants: {missing_fields}")

                    # Validation du rôle
                    if row['role'].lower() not in ['admin', 'teacher', 'student']:
                        raise ValueError("Rôle invalide (admin, teacher, student)")

                    # Hachage du mot de passe
                    hashed_pw = bcrypt.hashpw(
                        row['password'].encode(), 
                        bcrypt.gensalt()
                    ).decode()

                    # Insertion utilisateur
                    cursor.execute(
                        """INSERT INTO users 
                        (username, password_hash, role, nom, prenom, email, class_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            row['username'].lower(),
                            hashed_pw,
                            row['role'].lower(),
                            row['nom'].strip().title(),
                            row['prenom'].strip().title(),
                            row['email'].lower(),
                            row.get('class_id') if row.get('class_id') else None
                        )
                    )
                    inserted += 1

                except mysql.connector.IntegrityError as e:
                    error_msg = "Doublon détecté"
                    if "username" in str(e):
                        error_msg = "Nom d'utilisateur déjà existant"
                    elif "email" in str(e):
                        error_msg = "Email déjà utilisé"
                    errors.append({
                        'ligne': idx,
                        'erreur': error_msg,
                        'donnees': dict(row)
                    })
                except Exception as e:
                    errors.append({
                        'ligne': idx,
                        'erreur': str(e),
                        'donnees': dict(row)
                    })

            conn.commit()
            
            return {
                'success': len(errors) == 0,
                'inserted': inserted,
                'errors': errors,
                'message': f"{inserted} utilisateurs importés" + 
                          (f", {len(errors)} erreurs" if errors else "")
            }

    except Exception as e:
        return {
            'success': False,
            'message': f"Erreur de traitement : {str(e)}",
            'inserted': 0,
            'errors': []
        }

def _process_class_csv(reader):
    """Traitement spécifique pour les imports de classes"""
    try:
        with db_connection() as conn:
            cursor = conn.cursor()
            
            inserted = 0
            errors = []
            
            for idx, row in enumerate(reader, start=2):
                try:
                    # Nettoyage des données
                    row = {k.lower().strip(): v.strip() if isinstance(v, str) else v for k, v in row.items()}
                    
                    # Validation des données
                    required_fields = ['name', 'level', 'academic_year']
                    missing_fields = [field for field in required_fields if not row.get(field)]
                    if missing_fields:
                        raise ValueError(f"Champs manquants: {missing_fields}")
                    
                    cursor.execute(
                        """INSERT INTO classes 
                        (name, level, academic_year)
                        VALUES (%s, %s, %s)""",
                        (
                            row['name'].strip().upper(),
                            row['level'].strip().title(),
                            row['academic_year'].strip()
                        )
                    )
                    inserted += 1
                    
                except mysql.connector.IntegrityError:
                    errors.append({
                        'ligne': idx,
                        'erreur': "Classe déjà existante",
                        'donnees': dict(row)
                    })
                except Exception as e:
                    errors.append({
                        'ligne': idx,
                        'erreur': str(e),
                        'donnees': dict(row)
                    })

            conn.commit()
            
            return {
                'success': len(errors) == 0,
                'inserted': inserted,
                'errors': errors,
                'message': f"{inserted} classes importées" + 
                          (f", {len(errors)} erreurs" if errors else "")
            }

    except Exception as e:
        return {
            'success': False,
            'message': f"Erreur de traitement : {str(e)}",
            'inserted': 0,
            'errors': []
        }