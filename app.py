import os
import string
import random
import validators
import csv
import io
from datetime import datetime, timezone
from dateutil import parser
from flask import Flask, request, jsonify, redirect, Response
from pymongo import MongoClient
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flasgger import Swagger

app = Flask(__name__)

# Initialize Swagger UI (Available at /apidocs)
swagger = Swagger(app)

# Initialize Rate Limiter
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "100 per hour"],
    storage_uri="memory://"
)

# MongoDB Configuration
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client.snaplink
urls_collection = db.urls

# Create unique index to prevent collisions
urls_collection.create_index("short_hash", unique=True)

def generate_short_hash(length=6):
    characters = string.ascii_letters + string.digits
    while True:
        short_hash = ''.join(random.choices(characters, k=length))
        if not urls_collection.find_one({'short_hash': short_hash}):
            return short_hash

# --- API Endpoints ---

@app.route('/api/shorten', methods=['POST'])
@limiter.limit("10 per minute")
def shorten_url():
    """
    Shorten a long URL
    ---
    tags:
      - URL Operations
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - original_url
          properties:
            original_url:
              type: string
              example: "https://www.github.com"
            custom_alias:
              type: string
              example: "my-repo"
            expires_at:
              type: string
              format: date-time
              example: "2026-12-31T23:59:59Z"
    responses:
      201:
        description: URL shortened successfully
      400:
        description: Invalid input
      409:
        description: Custom alias already in use
    """
    data = request.get_json()
    
    if not data or 'original_url' not in data:
        return jsonify({'error': 'Missing original_url in request body'}), 400
        
    original_url = data['original_url']
    custom_alias = data.get('custom_alias')
    expires_at_str = data.get('expires_at')

    if not validators.url(original_url):
        return jsonify({'error': 'Invalid URL format provided'}), 400

    if custom_alias:
        if urls_collection.find_one({'short_hash': custom_alias}):
            return jsonify({'error': 'Custom alias already in use'}), 409
        short_hash = custom_alias
    else:
        short_hash = generate_short_hash()

    expires_at = None
    if expires_at_str:
        try:
            expires_at = parser.isoparse(expires_at_str)
        except ValueError:
            return jsonify({'error': 'Invalid expires_at format. Use ISO 8601.'}), 400

    new_url_document = {
        'original_url': original_url,
        'short_hash': short_hash,
        'clicks': 0,
        'created_at': datetime.now(timezone.utc),
        'expires_at': expires_at,
        'visits': [] # Array to hold timestamp and referrer for each click
    }
    
    urls_collection.insert_one(new_url_document)

    return jsonify({
        'message': 'URL shortened successfully',
        'short_url': f"{request.host_url}{short_hash}",
        'short_hash': short_hash,
        'original_url': original_url,
        'expires_at': expires_at.isoformat() if expires_at else None
    }), 201


@app.route('/<short_hash>', methods=['GET'])
def redirect_to_url(short_hash):
    """
    Redirect to original URL
    ---
    tags:
      - URL Operations
    parameters:
      - in: path
        name: short_hash
        required: true
        type: string
    responses:
      302:
        description: Redirects to original URL
      404:
        description: URL not found
      410:
        description: URL expired
    """
    url_entry = urls_collection.find_one({'short_hash': short_hash})
    
    if not url_entry:
        return jsonify({'error': 'URL not found'}), 404

    # Handle Link Expiration
    if url_entry.get('expires_at'):
        now = datetime.now(timezone.utc)
        expiration = url_entry['expires_at']
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
            
        if now > expiration:
            return jsonify({'error': 'This link has expired (410 Gone)'}), 410

    # Handle Referrer Tracking
    referrer = request.referrer or 'direct'
    visit_data = {
        'timestamp': datetime.now(timezone.utc),
        'referrer': referrer
    }

    # Increment clicks and push visit metadata atomically
    urls_collection.update_one(
        {'_id': url_entry['_id']},
        {
            '$inc': {'clicks': 1},
            '$push': {'visits': visit_data}
        }
    )
    
    return redirect(url_entry['original_url'])


@app.route('/api/stats/<short_hash>', methods=['GET'])
def url_stats(short_hash):
    """
    Get Link Analytics
    ---
    tags:
      - Analytics
    parameters:
      - in: path
        name: short_hash
        required: true
        type: string
    responses:
      200:
        description: Returns analytics payload
    """
    url_entry = urls_collection.find_one({'short_hash': short_hash})
    
    if url_entry:
        return jsonify({
            'original_url': url_entry['original_url'],
            'short_hash': url_entry['short_hash'],
            'clicks': url_entry['clicks'],
            'created_at': url_entry['created_at'].isoformat(),
            'expires_at': url_entry.get('expires_at').isoformat() if url_entry.get('expires_at') else None,
            'recent_referrers': url_entry.get('visits', [])[-5:] # Show last 5 visits
        }), 200
    else:
        return jsonify({'error': 'URL not found'}), 404

@app.route('/api/stats/export', methods=['GET'])
def export_stats_csv():
    """
    Export Analytics as CSV
    ---
    tags:
      - Analytics
    responses:
      200:
        description: CSV file download
    """
    urls = urls_collection.find()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Original URL', 'Short Hash', 'Total Clicks', 'Creation Date', 'Expiration Date', 'Top Referrer'])
    
    for url in urls:
        expires = url.get('expires_at').strftime('%Y-%m-%d %H:%M:%S') if url.get('expires_at') else 'N/A'
        
        # Calculate most common referrer
        visits = url.get('visits', [])
        referrers = [v.get('referrer') for v in visits if v.get('referrer')]
        top_referrer = max(set(referrers), key=referrers.count) if referrers else 'None'

        cw.writerow([
            str(url['_id']), 
            url['original_url'], 
            url['short_hash'], 
            url['clicks'], 
            url['created_at'].strftime('%Y-%m-%d %H:%M:%S'),
            expires,
            top_referrer
        ])
    
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = "attachment; filename=snaplink_analytics.csv"
    
    return output

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)