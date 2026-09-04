import pytest
from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Bypass rate limiting during tests
    app.config['RATELIMIT_ENABLED'] = False 
    
    with app.test_client() as client:
        yield client

def test_shorten_missing_url(client):
    response = client.post('/api/shorten', json={})
    assert response.status_code == 400
    assert b'Missing original_url' in response.data

def test_shorten_invalid_url(client):
    response = client.post('/api/shorten', json={'original_url': 'not-a-valid-url'})
    assert response.status_code == 400
    assert b'Invalid URL format' in response.data

def test_api_docs_available(client):
    response = client.get('/apidocs/')
    assert response.status_code == 200