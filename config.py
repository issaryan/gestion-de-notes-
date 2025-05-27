import os
from datetime import timedelta

# Configuration base de données
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),  
    'user': os.getenv('MYSQL_USER', 'ryan'),
    'password': os.getenv('MYSQL_PASSWORD', 'ryan'),
    'database': os.getenv('MYSQL_DB', 'academy_db'),
    'port': int(os.getenv('MYSQL_PORT', 3306)),  
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

# Configuration JWT
JWT_CONFIG = {
    'SECRET_KEY': os.getenv('JWT_SECRET', 'votre_clé_secrète_complexe_!12345'),
    'ALGORITHM': 'HS256',
    'ACCESS_TOKEN_EXPIRE_MINUTES': 60,  # 1 heure
    'REFRESH_TOKEN_EXPIRE_DAYS': 7
}
