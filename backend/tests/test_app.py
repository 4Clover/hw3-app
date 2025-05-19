# Following structure from: https://www.digitalocean.com/community/tutorials/unit-test-in-flask
# Following the basic structure on how to use pytest because I have never used it before
# Testing on: http://127.0.0.1:8000


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app 
import pytest
from flask import session

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

# ----- COMMENT & DEX UNIT TESTS -----

def test_add_comment(client, monkeypatch):
    
    # mock mongoDB so we don't need it to run this route
    class TestCollection:
        def insert_one(self, doc):
            class Result:
                inserted_id = "fakeID"
            return Result()
    
    
    import app
    app.comments_collection = TestCollection()
    fake_comment ={
        "articleId": "123",
        "author": "TEMP - Anon",
        "content": "I love puppies!"
    }
    response = client.post(f'/api/comments', json=fake_comment)
    assert response.status_code == 201
    comment = response.get_json()
    assert comment["articleId"] == "123"
    assert comment["author"] == "TEMP - Anon"
    assert comment["content"] == "I love puppies!"
    # timestamp and id are randomly generated but removed should be false
    assert comment["removed"] is False


def test_login(client):
    import os
    os.environ['OIDC_CLIENT_NAME'] = 'Flask App'
    class MockOAuthClient:
        def authorize_redirect(self, redirect_uri, **kwargs):
            from flask import redirect
            return redirect("http://fake-oauth-website.com/auth")
    
    # this passes mock OAuth registry
    class MockOAuth:
        pass
    # Using this: https://docs.python.org/3/library/functions.html#setattr
    # to help with mocking getattr(oauth, client_name)
    setattr(MockOAuth, "Flask App", MockOAuthClient())
    
    # replace the real OAuth registry with the fake
    import app
    app.oauth = MockOAuth()

    response = client.get('/api/login')
    assert response.status_code in (302, 303)
    assert response.headers["Location"] == "http://fake-oauth-website.com/auth" 


def test_authorize(client):
    import os
    os.environ['OIDC_CLIENT_NAME'] = 'Flask App'
    class MockOAuthClient:
        def authorize_access_token(self):
            return {"id_token": "456"}
        def parse_id_token(self, token, nonce=None):
            return {
                "email": "blah@fakeemail.com",
                "username": "testUserName",
                "userID": "789",
            }
    class MockOAuth:
        pass
    
    setattr(MockOAuth, "Flask App", MockOAuthClient())
    import app
    app.oauth = MockOAuth()

    # mock Users Collection
    class TestUsersCollection:
        def update_one(self, *args, **kwargs):
            return None
    
    app.users_collection = TestUsersCollection()

    with client.session_transaction() as mock_session:
        mock_session['nonce'] = 'test'
    
    response = client.get('/api/authorize')
    assert response.status_code in (302, 303)
    # it should redirect to the home page after this!
    assert response.location.startswith("http://localhost:5173")

def test_logout(client):
    # we don't need to mock the oauth on this one as we just need to clear the session!
    with client.session_transaction() as test_session:
        test_session['user'] = {'username': 'testUserName'}
    
    response = client.get('/api/logout')
    assert response.status_code in (302, 303)
    # the logout should redirect to '/' to the home page
    assert response.headers['Location'].endswith('/')
