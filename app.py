from flask import Flask, request, jsonify, redirect
from flask_sqlalchemy import SQLAlchemy
import string
import random
import validators
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urls.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Database Model ---
class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(2048), nullable=False)
    short_hash = db.Column(db.String(10), unique=True, nullable=False)
    clicks = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def generate_short_hash(length=6):
    characters = string.ascii_letters + string.digits
    while True:
        short_hash = ''.join(random.choices(characters, k=length))
        # Ensure the hash doesn't already exist
        if not URL.query.filter_by(short_hash=short_hash).first():
            return short_hash

# --- API Endpoints ---

@app.route('/api/shorten', methods=['POST'])
def shorten_url():
    data = request.get_json()
    
    if not data or 'original_url' not in data:
        return jsonify({'error': 'Missing original_url in request body'}), 400
        
    original_url = data['original_url']
    custom_alias = data.get('custom_alias')

    if not validators.url(original_url):
        return jsonify({'error': 'Invalid URL format provided'}), 400

    # Handle custom alias if provided
    if custom_alias:
        if URL.query.filter_by(short_hash=custom_alias).first():
            return jsonify({'error': 'Custom alias already in use'}), 409
        short_hash = custom_alias
    else:
        short_hash = generate_short_hash()

    new_url = URL(original_url=original_url, short_hash=short_hash)
    db.session.add(new_url)
    db.session.commit()

    return jsonify({
        'message': 'URL shortened successfully',
        'short_url': f"{request.host_url}{short_hash}",
        'short_hash': short_hash,
        'original_url': original_url
    }), 201


@app.route('/<short_hash>', methods=['GET'])
def redirect_to_url(short_hash):
    url_entry = URL.query.filter_by(short_hash=short_hash).first()
    
    if url_entry:
        url_entry.clicks += 1
        db.session.commit()
        return redirect(url_entry.original_url)
    else:
        return jsonify({'error': 'URL not found'}), 404


@app.route('/api/stats/<short_hash>', methods=['GET'])
def url_stats(short_hash):
    url_entry = URL.query.filter_by(short_hash=short_hash).first()
    
    if url_entry:
        return jsonify({
            'original_url': url_entry.original_url,
            'short_hash': url_entry.short_hash,
            'clicks': url_entry.clicks,
            'created_at': url_entry.created_at.isoformat()
        }), 200
    else:
        return jsonify({'error': 'URL not found'}), 404

# Initialize DB before first request
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)