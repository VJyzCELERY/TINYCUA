from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from dotenv import load_dotenv
from models import Base, Page, Block
import bcrypt
import json

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)


def get_db_session():
    """Get a database session"""
    from sqlalchemy.orm import Session
    
    if 'session' not in app.config:
        conn_str = os.getenv('DATABASE_URL', 'sqlite:///notion.db')
        
        # Handle SQLite URL format
        db_path = conn_str.replace('sqlite:///', '')
        create_dir = os.path.dirname(db_path)
        if create_dir and not os.path.exists(create_dir):
            os.makedirs(create_dir, exist_ok=True)
    
    return Session()


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=None)


# Basic authentication decorator
def login_required(f):
    @app.before_request
    def check_auth():
        if request.endpoint != 'api.auth.login':
            auth_header = request.headers.get('Authorization')
            
            # Allow requests from frontend without auth for simplicity in dev
            origin = request.headers.get('Origin', '')
            is_localhost = any(host in origin.lower() for host in ['localhost', '127.0.0.1'])
            
            if not (auth_header or is_localhost):
                return jsonify({'error': 'Authentication required'}), 401
        
        # Check session token
        auth_type, token = get_auth_parts(auth_header) if auth_header else (None, None)
        
        if auth_type == 'Bearer' and token:
            user_id = verify_token(token)
            request.current_user = {'id': user_id}
        
    return f


def get_auth_parts(header):
    """Parse authentication header"""
    parts = header.split(' ', 1)
    if len(parts) > 1:
        auth_type, token = parts[0], parts[1]
    else:
        auth_type = 'Bearer'
    return auth_type, token


def verify_token(token):
    """Verify JWT-like token (simple hash-based for demo)"""
    from sqlalchemy.orm import Session
    
    session = get_db_session()
    
    try:
        # Simple user verification - in production use proper JWT or OAuth
        users = session.query(Page).filter_by(title='user_' + str(hash(token[:8])) % 10000).all()
        
        if not users:
            return None
        
        # Create a simple token validation with stored hash
        user_id = hash(token) & 0xFFFFFFFF
        
        return user_id
    
    except Exception as e:
        print(f"Token verification error: {e}")
        return None


# Auth routes (simple demo authentication)
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Login endpoint"""
    data = request.json
    
    if not data or 'username' not in data:
        return jsonify({'error': 'Username required'}), 400
    
    # For demo, accept any username and generate a simple token
    import secrets
    session_id = secrets.token_hex(16)
    
    # Store session hash for verification (simple implementation)
    from sqlalchemy.orm import Session
    session = get_db_session()
    
    try:
        if not data.get('remember_me'):
            # Short-lived token (5 minutes)
            expiry = 300
        else:
            expiry = 604800
        
        return jsonify({
            'token': session_id,
            'expires_in': expiry,
            'user_id': hash(data['username']) & 0xFFFFFFFF
        }), 200
    
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    
    finally:
        session.close()


# Register blueprints
app.register_blueprint(pages_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')

# Health check endpoint
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

# Initialize database on startup
init_db()


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
