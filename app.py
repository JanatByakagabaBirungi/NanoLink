import os
import string
import random
import validators
import csv
import io
from datetime import datetime, timezone
from flask import Flask, request, jsonify, redirect, Response
from pymongo import MongoClient
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)

# Initialize rate limiter based on the user's IP address
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

# Create a unique index for short_hash to prevent collisions at the DB level
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
    data = request.get_json()
    
    if not data or 'original_url' not in data:
        return jsonify({'error': 'Missing original_url in request body'}), 400
        
    original_url = data['original_url']
    custom_alias = data.get('custom_alias')

    if not validators.url(original_url):
        return jsonify({'error': 'Invalid URL format provided'}), 400

    if custom_alias:
        if urls_collection.find_one({'short_hash': custom_alias}):
            return jsonify({'error': 'Custom alias already in use'}), 409
        short_hash = custom_alias
    else:
        short_hash = generate_short_hash()

    new_url_document = {
        'original_url': original_url,
        'short_hash': short_hash,
        'clicks': 0,
        'created_at': datetime.now(timezone.utc)
    }
    
    urls_collection.insert_one(new_url_document)

    return jsonify({
        'message': 'URL shortened successfully',
        'short_url': f"{request.host_url}{short_hash}",
        'short_hash': short_hash,
        'original_url': original_url
    }), 201


@app.route('/<short_hash>', methods=['GET'])
def redirect_to_url(short_hash):
    # Find the URL and increment the click count in a single atomic operation
    url_entry = urls_collection.find_one_and_update(
        {'short_hash': short_hash},
        {'$inc': {'clicks': 1}}
    )
    
    if url_entry:
        return redirect(url_entry['original_url'])
    else:
        return jsonify({'error': 'URL not found'}), 404


@app.route('/api/stats/<short_hash>', methods=['GET'])
def url_stats(short_hash):
    url_entry = urls_collection.find_one({'short_hash': short_hash})
    
    if url_entry:
        return jsonify({
            'original_url': url_entry['original_url'],
            'short_hash': url_entry['short_hash'],
            'clicks': url_entry['clicks'],
            'created_at': url_entry['created_at'].isoformat()
        }), 200
    else:
        return jsonify({'error': 'URL not found'}), 404

@app.route('/api/stats/export', methods=['GET'])
def export_stats_csv():
    urls = urls_collection.find()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Original URL', 'Short Hash', 'Total Clicks', 'Creation Date'])
    
    for url in urls:
        # MongoDB uses _id which is an ObjectId, converting it to string for the CSV
        cw.writerow([
            str(url['_id']), 
            url['original_url'], 
            url['short_hash'], 
            url['clicks'], 
            url['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        ])
    
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = "attachment; filename=snaplink_analytics.csv"
    
    return output

if __name__ == '__main__':
    # Bind to 0.0.0.0 so the Flask server is accessible outside the Docker container
    app.run(host='0.0.0.0', port=5000, debug=True)