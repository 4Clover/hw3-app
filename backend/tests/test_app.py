# Following structure from: https://www.digitalocean.com/community/tutorials/unit-test-in-flask
# Following the basic structure on how to use pytest because I have never used it before
# Testing on: http://127.0.0.1:8000

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app 
import pytest

@pytest.fixture
def client():
    # Test: finding client (diff-level: easy)
    with app.test_client() as client:
        yield client
# Alyssa's tests only : Start 
def test_getKey(client):
    # This test case works only for default fake key!
    # Do not put a real key before using this suite!
    response = client.get('/api/getKey')
    assert response.status_code == 200
    assert response.json == {"message": "super_secret_key"}

def test_searchArticles(client):
    # Test: test searchArticles route (diff-level: mid)
    # This test does work!
    # However, setting it to 400 because I do not want to expose my key!
    response = client.get('/api/searchArticles')
    assert response.status_code == 200
    assert response.json == {"message": "Error!"}

def test_non_existent_route(client):
    # Test: non-existant route (diff-level: easy)
    response = client.get('/non-existent')
    assert response.status_code == 404

# Dillion's tests (created by Alyssa :D)
def test_fake_search(client):
    response = client.get('/api/test_articles')
    assert response.status_code == 200
    assert response.json[0]["author"] == "Zesty Lemonsworth"
    assert response.json[0]["content"] == "Citizens storm supermarkets as lime shelves empty overnight..."
    assert response.json[0]["headline"] == "Breaking: Lime Shortage Sparks Citrus Panic"
    assert response.json[0]["id"] == "nyt1"
    assert response.json[0]["imageUrl"] == "/images/1.png"

# Just checking the to see if the articleUrl exists!
# These response jsons will vary in response so this is the only thing we can test that will
# usually show a consistent result
def test_search(client):
    # similar to above test_searchArticles, need a valid key or else it will fail!
    # do not test_getKey if you are going to run this test!
    query = 'davis'
    response = client.get(f'/api/search?query={query}')
    assert response.status_code == 200
    assert response.json[0]["articleUrl"].startswith("https://www.nytimes.com/")

def test_bad_search(client):
    query = "limes"
    response = client.get(f'/api/search?query={query}')
    assert response.status_code == 500
    assert response.json == {"error": f"Invalid search query: {query}. Please try again later."}