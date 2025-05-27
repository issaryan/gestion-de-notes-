# backend/server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import jwt
import mysql.connector
from urllib.parse import urlparse, parse_qs
import bcrypt
from urllib.parse import parse_qs
import os
from datetime import datetime, timedelta
from backend.database import init_db, add_class, add_subject, add_grade, db_connection
from backend.csv_processor import process_csv, process_grades_csv
from backend.pdf_generator import generate_student_transcript, generate_class_report
from backend.config import DB_CONFIG
import re
from backend.auth import login_user
from backend.config import JWT_CONFIG  # Import absolu

# Configuration importée depuis config.py
from backend.config import JWT_CONFIG, DB_CONFIG
MAX_FILE_SIZE = 10 * 1024 * 1024

class RESTRequestHandler(BaseHTTPRequestHandler):

    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        
        # Configuration CORS dynamique
        if os.getenv('ENV') == 'development':
            self.send_header('Access-Control-Allow-Origin', 'http://localhost:4200')
        else:
            self.send_header('Access-Control-Allow-Origin', 'https://votre-domaine.com')
        
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Requested-With')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()
    
    # Helper methods
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:4200')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type, X-Requested-With')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()

    def _parse_json(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return None
        return json.loads(self.rfile.read(content_length))

    def _get_token(self):
        auth_header = self.headers.get('Authorization', '')
        return auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None

    def _verify_token(self, required_roles=None):
        token = self._get_token()
        if not token:
            return None
        
        try:
            payload = jwt.decode(
                token, 
                JWT_CONFIG['SECRET_KEY'], 
                algorithms=[JWT_CONFIG['ALGORITHM']]
            )
            
            if datetime.utcnow().timestamp() > payload.get('exp', 0):
                return None

            with db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT role FROM users WHERE id = %s", (payload['sub'],))
                    result = cursor.fetchone()
                    if not result:
                        return None
                    user_role = result[0]

            if required_roles and user_role not in required_roles:
                return None
            
            return {'user_id': payload['sub'], 'role': user_role}
        
        except jwt.PyJWTError:
            return None

    def _send_response(self, data, status=200, content_type='application/json'):
        self._set_headers(status, content_type)
        if isinstance(data, bytes):
            self.wfile.write(data)
        else:
            self.wfile.write(json.dumps(data).encode('utf-8'))

    # Handlers
    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        # Public endpoints
        if path == '/api/health':
            return self._send_response({'status': 'OK'})

        # Authenticated endpoints
        user = self._verify_token()
        if not user:
            return self._send_response({'error': 'Unauthorized'}, 401)

        try:
            with db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                if path == '/api/users/me':
                    cursor.execute('''
                        SELECT u.id, u.username, u.role, u.nom, u.prenom, u.email, 
                               DATE_FORMAT(u.last_login, '%Y-%m-%d %H:%i:%s') as last_login,
                               c.name as class_name
                        FROM users u
                        LEFT JOIN classes c ON u.class_id = c.id
                        WHERE u.id = %s
                    ''', (user['user_id'],))
                    return self._send_response(cursor.fetchone())

                elif path == '/api/users':
                    if user['role'] == 'admin':
                        search_term = f"%{query.get('search', [''])[0]}%"
                        cursor.execute('''
                            SELECT u.id, u.username, u.role, u.nom, u.prenom, u.email, 
                                   c.name as class_name,
                                   CASE WHEN u.last_login > DATE_SUB(NOW(), INTERVAL 6 MONTH)
                                        THEN 'Actif' ELSE 'Inactif' END AS status
                            FROM users u
                            LEFT JOIN classes c ON u.class_id = c.id
                            WHERE username LIKE %s OR nom LIKE %s OR prenom LIKE %s
                        ''', (search_term, search_term, search_term))

                    elif user['role'] == 'teacher':
                        cursor.execute('''
                            SELECT u.id, u.nom, u.prenom, u.email, c.name as class_name
                            FROM users u
                            JOIN classes c ON u.class_id = c.id
                            JOIN subjects s ON c.id = s.class_id
                            WHERE s.teacher_id = %s AND u.role = 'student'
                        ''', (user['user_id'],))
                    
                    return self._send_response(cursor.fetchall())

                elif re.match(r'^/api/classes/\d+$', path):
                    class_id = path.split('/')[-1]
                    cursor.execute('''
                        SELECT c.*, COUNT(u.id) as student_count, 
                               AVG(g.grade) as average_grade
                        FROM classes c
                        LEFT JOIN users u ON c.id = u.class_id AND u.role = 'student'
                        LEFT JOIN grades g ON u.id = g.student_id
                        WHERE c.id = %s
                        GROUP BY c.id
                    ''', (class_id,))
                    class_data = cursor.fetchone()
                    if not class_data:
                        return self._send_response({'error': 'Class not found'}, 404)

                    cursor.execute('''
                        SELECT s.id, s.name, CONCAT(u.prenom, ' ', u.nom) as teacher
                        FROM subjects s
                        JOIN users u ON s.teacher_id = u.id
                        WHERE s.class_id = %s
                    ''', (class_id,))
                    class_data['subjects'] = cursor.fetchall()
                    return self._send_response(class_data)

                elif path.startswith('/api/report/student/'):
                    student_id = path.split('/')[-1]
                    if user['role'] == 'teacher':
                        cursor.execute('''
                            SELECT 1 FROM subjects s
                            JOIN users u ON s.class_id = u.class_id
                            WHERE s.teacher_id = %s AND u.id = %s
                        ''', (user['user_id'], student_id))
                        if not cursor.fetchone():
                            return self._send_response({'error': 'Forbidden'}, 403)

                    pdf_data = generate_student_transcript(student_id)
                    return self._send_response(pdf_data, content_type='application/pdf')

                elif path == '/api/schedule':
                    cursor.execute('''
                        SELECT s.day, s.start_time, s.end_time, 
                               subj.name as subject_name,
                               c.name as class_name
                        FROM schedule s
                        JOIN subjects subj ON s.subject_id = subj.id
                        JOIN classes c ON subj.class_id = c.id
                        WHERE subj.teacher_id = %s
                    ''', (user['user_id'],))
                    return self._send_response(cursor.fetchall())

                elif path == '/api/subjects':
                    user = self._verify_token(['teacher', 'admin'])
                    if not user:
                        return self._send_response({'error': 'Unauthorized'}, 401)
                    
                    cursor.execute('''
                        SELECT s.id, s.name, c.name as class_name,
                            COUNT(u.id) as student_count
                        FROM subjects s
                        JOIN classes c ON s.class_id = c.id
                        LEFT JOIN users u ON c.id = u.class_id
                        WHERE s.teacher_id = %s
                        GROUP BY s.id
                    ''', (user['user_id'],))
                    return self._send_response(cursor.fetchall())
                elif path == '/api/grades' or re.match(r'^/api/grades/\d+$', path):
                    user = self._verify_token()
                    student_id = path.split('/')[-1] if re.match(r'^/api/grades/\d+$', path) else None
                    
                    if student_id and user['role'] == 'student' and int(student_id) != user['user_id']:
                        return self._send_response({'error': 'Forbidden'}, 403)
                    
                    query = '''
                        SELECT g.*, s.name as subject, u.nom as teacher_name 
                        FROM grades g
                        JOIN subjects s ON g.subject_id = s.id
                        JOIN users u ON s.teacher_id = u.id
                    ''' + (f" WHERE g.student_id = {student_id}" if student_id else "")
                    cursor.execute(query)
                    return self._send_response(cursor.fetchall())

                else:
                    return self._send_response({'error': 'Not Found'}, 404)

        except Exception as e:
            return self._send_response({'error': str(e)}, 500)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == '/api/login':
            data = self._parse_json()
            if not data or 'username' not in data or 'password' not in data:
                return self._send_response({'error': 'Invalid credentials'}, 400)

            try:
                from backend.auth import login_user
                auth_response = login_user(data['username'], data['password'])
                return self._send_response(auth_response)

            except Exception as e:
                return self._send_response({'error': str(e)}, 500)

        elif path == '/api/upload':
            user = self._verify_token(['admin', 'teacher'])
            if not user:
                return self._send_response({'error': 'Unauthorized'}, 401)

            try:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={'REQUEST_METHOD': 'POST'}
                )
                file_item = form['file'] if 'file' in form else None

                if not file_item or not file_item.file:
                    return self._send_response({'error': 'No file uploaded'}, 400)

                file_data = file_item.file.read()
                if len(file_data) > MAX_FILE_SIZE:
                    return self._send_response({'error': 'File too large'}, 413)

                if user['role'] == 'admin':
                    result = process_csv(file_data.decode('utf-8'))
                else:
                    result = process_grades_csv(file_data.decode('utf-8'), user['user_id'])

                return self._send_response(result, 201)

            except Exception as e:
                return self._send_response({'error': str(e)}, 500)

        else:
            return self._send_response({'error': 'Not Found'}, 404)

    def do_PUT(self):

        data = self._parse_json()
        if not data:
            return self._send_response({'error': 'Invalid data'}, 400)
            
        valid_days = {'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT'}
        for entry in data:
            if entry['day'].upper() not in valid_days:
                raise ValueError(f"Jour invalide : {entry['day']}")
        path = urlparse(self.path).path
        user = self._verify_token(['admin', 'teacher'])
        if not user:
            return self._send_response({'error': 'Unauthorized'}, 401)

        if path == '/api/schedule':
            try:
                data = self._parse_json()
                if not data or not isinstance(data, list):
                    return self._send_response({'error': 'Invalid data'}, 400)

                with db_connection() as conn:
                    cursor = conn.cursor()
                    subject_ids = {entry.get('subject_id') for entry in data}

                    # Vérification des permissions
                    cursor.execute('''
                        SELECT id FROM subjects 
                        WHERE teacher_id = %s AND id IN (%s)
                    ''' % (user['user_id'], ','.join(map(str, subject_ids)) if subject_ids else 'NULL'))
                    valid_subjects = {row[0] for row in cursor.fetchall()}

                    if len(valid_subjects) != len(subject_ids):
                        return self._send_response({'error': 'Unauthorized subjects'}, 403)

                    # Mise à jour de l'emploi du temps
                    cursor.execute('DELETE FROM schedule WHERE subject_id IN (%s)' % ','.join(map(str, valid_subjects)))
                    
                    for entry in data:
                        cursor.execute('''
                            INSERT INTO schedule 
                            (subject_id, day, start_time, end_time)
                            VALUES (%s, %s, %s, %s)
                        ''', (
                            entry['subject_id'],
                            entry['day'].upper(),
                            entry['start_time'],
                            entry['end_time']
                        ))

                    conn.commit()
                    return self._send_response({'success': True})

            except Exception as e:
                return self._send_response({'error': str(e)}, 500)

        else:
            return self._send_response({'error': 'Not Found'}, 404)
    def do_DELETE(self):
        user = self._verify_token(['admin'])
        if not user:
            return self._send_response({'error': 'Unauthorized'}, 401)
        
        path = urlparse(self.path).path
        if re.match(r'^/api/users/\d+$', path):
            user_id = path.split('/')[-1]
            with db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
                conn.commit()
            return self._send_response({'success': True})

if __name__ == '__main__':
    os.makedirs('reports', exist_ok=True)
    init_db()
    server_address = ('0.0.0.0', 8000)
    httpd = HTTPServer(server_address, RESTRequestHandler)
    print(f"Server running on http://{server_address[0]}:{server_address[1]}")
    httpd.serve_forever()
