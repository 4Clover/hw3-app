import time

from bson import ObjectId
from flask import Flask, jsonify, send_from_directory, request, redirect, session
import os, requests
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING
from authlib.common.security import generate_token
from authlib.integrations.flask_client import OAuth


# CONSTANTS
# directory from which the assets created by the frontend build process are located.
BUILD_DIR = os.path.join(os.path.dirname(__file__), "build")
NYT_SAC_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json?q=sacramento&begin_date=20250404&end_date=20250428&timestags.location.includes=california&api-key="
NYT_DAVIS_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json?q=%22Davis,%20California%22&begin_date=20210301&api-key="
BASE_NYT_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

# flask app init, servers all static files from the build directory to the frontend
app = Flask(__name__, static_folder=os.path.join(BUILD_DIR), static_url_path='/')
CORS(app)  # this is the function to allow for different front and backend IP's when developing

app.secret_key = os.urandom(24)


oauth = OAuth(app)

nonce = generate_token()

# ---------- DEX SET UP  ----------
oauth.register(
    name=os.getenv('OIDC_CLIENT_NAME'),
    client_id=os.getenv('OIDC_CLIENT_ID'),
    client_secret=os.getenv('OIDC_CLIENT_SECRET'),
    #server_metadata_url='http://dex:5556/.well-known/openid-configuration',
    authorization_endpoint="http://localhost:5556/auth",
    token_endpoint="http://dex:5556/token",
    jwks_uri="http://dex:5556/keys",
    userinfo_endpoint="http://dex:5556/userinfo",
    device_authorization_endpoint="http://dex:5556/device/code",
    client_kwargs={'scope': 'openid email profile'}
)

# mongo connection
comments_collection = None # init to none due to mongo type oddities
try:
    mongo_uri = os.getenv("MONGO_URI")
    client = MongoClient(mongo_uri)
    db_name = "CommentDB"
    db = client[db_name]
    comments_collection = db["comments"]
    # this collection tracks articles and comments under the 
    app.logger.info(f"Connected to MongoDB! Database: {db.name}. Comments collection ready.")
    # adding users collection to keep track of users in database
    users_collection = db["users"]
    app.logger.info(f"Database {db.name} successfully created collection: users!")
except Exception as e:
    app.logger.error(f"Error connecting to MongoDB or comments collection: {e}")

# Initialize users in database
def initialize_users():
    users_collection.insert_one({
        "email": "admin@hw3.com",
        "hash": "$2b$10$8NoCpIs/Z6v0s/pU9YxYIO10uWyhIVOS2kmNac9AD0HsqRhP5dUie", 
        "username": "admin",
        "userID": "123"
    })
    users_collection.insert_one({
        "email": "moderator@hw3.com",
        "hash": "$2b$12$2aaoZyVjMWvoCq.DmCUECOGoW0oaBCyzSluUm3BpLrP26sVT71PSC", 
        "username": "moderator",
        "userID": "456"
    })
    users_collection.insert_one({
        "email": "user@hw3.com",
        "hash": "$2b$12$321HomfT164U9f5l.xQaYuHThGCss8PRPNy8t./tq8Frgr6UYeEka", 
        "username": "user",
        "userID": "789"
    })
    print("Initialized all users...")

# helper for serializing MongoDB ObjectId
def serialize_doc(doc):
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

def get_key():
    api_key = os.getenv("NYT_API_KEY")
    if not api_key or api_key == "super_secret_key":
        app.logger.error("NYT_API_KEY environment variable not set.")
        return None
    return api_key

# ------------ DEX API ENDPOINTS ---------------
@app.route('/api/getUser')
def get_user():
    user = session.get('user')
    if user:
        return jsonify({"user_email": {user['email']}})
    return jsonify({"no_email": ""})

@app.route('/api/login')
def login():
    session['nonce'] = nonce
    redirect_uri = 'http://localhost:8000/authorize'
    return oauth.flask_app.authorize_redirect(redirect_uri, nonce=nonce)

@app.route('/api/authorize')
def authorize():
    token = oauth.flask_app.authorize_access_token()
    nonce = session.get('nonce')

    user_info = oauth.flask_app.parse_id_token(token, nonce=nonce)  # or use .get('userinfo').json()
    session['user'] = user_info
    return redirect('/')

@app.route('/api/logout')
def logout():
    session.clear()
    return redirect('/')

# ------------ MONGO API ENDPOINTS ---------------
@app.route("/api/comments", methods=["POST"])
def add_comment():
    if comments_collection is None:
        return jsonify({"error": "Database service not available"}), 503
    try:
        data = request.get_json()
        # check if formatting matches frontend
        if not data or 'content' not in data or 'author' not in data or 'articleId' not in data:
            return jsonify({"error": "Missing articleId, author, or content in request"}), 400

        comment_doc = {
            "articleId": str(data["articleId"]), # str cast to ensure consistency
            "author": data["author"],
            "content": data["content"],
            "timestamp": time.time(),  # UNIX timestamp (float)
            "removed": False,
            "removedBy": ""
        }
        result = comments_collection.insert_one(comment_doc)

        # new comment in frontend structure
        created_comment_response = {
            "id": str(result.inserted_id),
            "articleId": comment_doc["articleId"],
            "author": comment_doc["author"],
            "content": comment_doc["content"],
            "removed": comment_doc["removed"],
            "removedBy": comment_doc["removedBy"],
            "timestamp": comment_doc["timestamp"]
        }
        return jsonify(created_comment_response), 201

    except Exception as error:
        app.logger.error(f"Error adding comment: {error}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(error)}"}), 500

def serialize_comment_for_frontend(comment_doc):
    if not comment_doc:
        return None
    return {
        "id": str(comment_doc["_id"]),
        "articleId": comment_doc.get("articleId", ""), # must be present
        "author": comment_doc.get("author", "Anonymous"),
        "content": comment_doc.get("content", ""),
        "removed": comment_doc.get("removed", False),
        "removedBy": comment_doc.get("removedBy", ""),
        "timestamp": comment_doc.get("timestamp")
    }

@app.route("/api/comments", methods=["GET"])
def get_all_comments():
    if comments_collection is None:
        return jsonify({"error": "Database service not available"}), 503
    try:
        # fetch and sort by newest (DESCENDING)
        all_db_comments = list(comments_collection.find().sort("timestamp", DESCENDING))

        serialized_comments = [serialize_comment_for_frontend(comment) for comment in all_db_comments]
        # filter None's i.e., failed or missing data
        serialized_comments = [c for c in serialized_comments if c and c.get("articleId")]

        return jsonify(serialized_comments), 200

    except Exception as error:
        app.logger.error(f"Error fetching comments: {error}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(error)}"}), 500

# unused current, I think useful for moderation
@app.route("/api/comments/<comment_id>", methods=["GET"])
# TODO: get_comment_count function that gets num of comments per post for frontend display :)
def get_comment_count():
    count = 0
    return count

def get_comment_by_id(comment_id):
    if comments_collection is None:
        return jsonify({"error": "Database service not available"}), 503
    try:
        comment = comments_collection.find_one({"_id": ObjectId(comment_id)})
        if comment:
            return jsonify(serialize_comment_for_frontend(comment)), 200
        else:
            return jsonify({"error": "Comment not found"}), 404
    except Exception as error:
        app.logger.error(f"Error fetching comment by ID: {error}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(error)}"}), 500

# TODO: Add moderator change, delete, and update endpoints
# Redacted text per HW should be replaced with Unicode character 'FULL BLOCK' (U+2588) -- possibly done via frontend?

# alyssa -------------------------------------------------
@app.get('/api/searchArticles')
def get_Key_and_Articles():
    # help from CourseAssist (see aiUsage.txt) and
    # https://www.w3schools.com/python/module_requests.asp
    apiKey =  os.getenv('NYT_API_KEY') # naming convention is against PEP8
    full_url = NYT_SAC_URL + apiKey
    response = requests.get(full_url)
    if response.status_code != 200:
        return jsonify({"message": "Error!"})
    else:
        return jsonify(response.json())

@app.route("/api/getKey")
def getKey(): # naming convention is against PEP8
    # Note: This function is only for testing! Do not test unless you want to reveal your key
    # unless you want the searchArticles route to not work!
    return jsonify({"message": os.getenv('NYT_API_KEY')})
# ----------------------------------------------------------


# article testing endpoint
@app.route("/api/test_articles") # temp -- will delete at some point
def get_articles():
    try:
        # placeholder data - replace this with actual NYT API calls
        placeholder_articles = [
            # data mockup, fits the current placeholder HTML hardcoded in the frontend
            {"id": "nyt1", "headline": "Breaking: Lime Shortage Sparks Citrus Panic", "imageUrl": "/images/1.png",
             "author": "Zesty Lemonsworth",
             "content": "Citizens storm supermarkets as lime shelves empty overnight..."},
            {"id": "nyt2", "headline": "Exclusive Interview: \"Life as a Lime Farmer\"", "imageUrl": "/images/2.png",
             "author": "Margarita Limeberg", "content": "Farmer Zest McJuicy reveals secrets..."},
            {"id": "nyt3", "headline": "Opinion: Is Lime the New Lemon?", "imageUrl": "/images/3.png",
             "author": "Citrus McPeel", "content": "Lemon lobbyists are furious..."},
            {"id": "nyt4", "headline": "Study Reveals 9 Out of 10 Doctors Recommend More Limes",
             "imageUrl": "/images/5.png", "author": "Dr. Key Limeman",
             "content": "'Sourness improves your mood,' scientists confirm..."},
            {"id": "nyt5", "headline": "Sports Update: Limetown Limers Win the Citrus Cup", "imageUrl": "/images/6.png",
             "author": "Coach Ricky Rind", "content": "Fans chant, 'When life gives you limes...'"},
            {"id": "nyt6", "headline": "Technology Breakthrough: Smartphone Now Charges Using Limes",
             "imageUrl": "/images/7.png", "author": "Elon Zest", "content": "Tech company CEO proudly announces..."},
            {"id": "nyt7", "headline": "Travel Guide: Top 5 Lime-Themed Destinations", "imageUrl": "/images/1.png",
             "author": "Clementine Sourwood", "content": "Visit Lime Island, Limetown..."},
            {"id": "nyt8", "headline": "Economics: LimeCoin Cryptocurrency Hits Record High",
             "imageUrl": "/images/8.png", "author": "Warren Zuffet",
             "content": "Investors advise: 'Buy low, zest high.'"},
            {"id": "nyt9", "headline": "Cooking Tips: How to Lime Your Way to Culinary Stardom",
             "imageUrl": "/images/9.png", "author": "Chef Zestina Peelini",
             "content": "'A lime a day keeps blandness away,' celebrity chef advises."},
            {"id": "nyt10", "headline": "Crime Report: Lime Bandits Strike Again", "imageUrl": "/images/1.png",
             "author": "Detective Perry Limecroft", "content": "Thieves apprehended after stealing 1,000 limes..."},
            {"id": "nyt11", "headline": "Weather Forecast: Heavy Lime Showers Expected", "imageUrl": "/images/12.png",
             "author": "Sunny Citrina", "content": "Meteorologists warn residents to carry cocktail umbrellas..."},
            {"id": "nyt12", "headline": "Science: Lime Juice Found on Mars", "imageUrl": "/images/10.png",
             "author": "Neil Zestrong", "content": "NASA confirms, 'The red planet is now officially zesty.'"}
        ]
        return jsonify(placeholder_articles)
    except Exception as e:
        app.logger.error(f"Error fetching placeholder articles: {e}")
        return jsonify({"error": "Failed to load articles"}), 500

# parse API data into dictionary for frontend
def parse_article_data(article):
        try:
            headline_obj = article.get('headline', {}) # headline dict
            main_headline = headline_obj.get('main', 'No Headline Available') # string
            byline_obj = article.get('byline', {}) # byline dict
            original_byline = byline_obj.get('original', '') # string
            author = original_byline.removeprefix('By ').strip() if original_byline else 'Unknown Author' # strip 'By' if on author
            content_summary = article.get('abstract', article.get('snippet', 'No summary available')) # option for if the abstract is not available, but likely never to be used
            multimedia = article.get('multimedia')
            # aria image text here?
            article_id = article.get('_id', None)
            web_url = article.get('web_url', '# ')
            image_url = None

            # article_id required for column population on frontend
            if not article_id:
                app.logger.error(f"Article missing _id: {article}")
                return None

            # type check for if the multimedia of an article even exits or is properly formatted
            if multimedia and isinstance(multimedia, dict):
                default_image_dict = multimedia.get('default', '')
                if isinstance(default_image_dict, dict) and default_image_dict.get('url'):
                    image_url = default_image_dict.get('url')

            return { # dictionary
                'id': article_id,
                'headline': main_headline,
                'author': author,
                'content': content_summary,
                'imageUrl': image_url, # none if no image found
                'articleUrl': web_url
            }
        except Exception as e:
            app.logger.error(f"Error parsing article data for article ID {article.get('_id', 'N/A')}: {e}", exc_info=True) # includes exc for ease of debugging
            return None

@app.route("/api/search")
def fetch_nyt_articles():
    api_key = get_key()
    if not api_key:
        return jsonify({"error": "Server error: NYT API key not set."}), 500 # send error to frontend to show on webpage
    processed_articles = []

    search_query = request.args.get('query')
    if search_query not in ['davis', 'sacramento', 'Davis, California', 'Sacramento, California', 'Sacramento', 'Davis']:
        return jsonify({"error": f"Invalid search query: {search_query}. Please try again later."}), 500

    search_begin = request.args.get('begin')
    search_end = request.args.get('end')
    search_filter = request.args.get('filter') # None most of the time
    search_page = request.args.get('page', default=0, type=int)
    # debug info for reference, check vite.config.ts for what is actually being sent
    app.logger.info(f"Search query:'{search_query}', Filter:'{search_filter}', Page:'{search_page}'")
    params = {
        'q': search_query,
        'api-key': api_key,
        'page': search_page,
    }
    if search_begin:
        params['begin_date'] = search_begin # format year-month-day (no dashes!)
    if search_end:
        params['end_date'] = search_end # same thing here (ex: 20250401)
    if search_filter: # add fq as a param if it actually has something, the added '&' would break the API call otherwise
        params['fq'] = search_filter

    # docs reference:
        # payload = {'key1': 'value1', 'key2': ['value2', 'value3']}
        # r = requests.get('https://httpbin.org/get', params=payload)
        # print(r.url)
        # https://httpbin.org/get?key1=value1&key2=value2&key2=value3

    try:
        nyt_req = requests.get(BASE_NYT_URL, params=params)
        # check for an HTTP error
        nyt_req.raise_for_status()

        nyt_data = nyt_req.json()

        # structure check
        articles_list = nyt_data['response']['docs'] # error check on data structure can go here
        # end structure check

        for article in articles_list:
            parsed_article = None
            if isinstance(article, dict) : parsed_article = parse_article_data(article) # type check before parse
            if parsed_article:
                processed_articles.append(parsed_article)
            else : app.logger.warning(f"Article is not a dict - skipped: {article}")
        return jsonify(processed_articles)

    except Exception as e:
        app.logger.error(f"An error occurred while fetching NYT articles: {e}")
        return jsonify({"error": "An unexpected error occurred. Please try again later."}), 500


@app.route("/test/test-mongo")
def test_mongo_connection():
    if not client: # check if client exists
        return jsonify({"error": "MongoDB client not initialized"}), 503
    try:
        server_info = client.server_info() # "pings" the server
        return jsonify({
            "message": "Successfully connected to MongoDB!",
            "server_version": server_info.get('version'),
            "collections": db.list_collection_names() if not db is None else "Database not initialized" # must be None comparison as object isnt truth/falsy
        })
    except Exception as e:
        app.logger.error(f"MongoDB connection test failed: {e}")
        return jsonify({"error": f"MongoDB connection test failed: {str(e)}"}), 500

# server frontend HTML (svelte)
@app.route('/')
@app.route("/<path:path>")
def serve_frontend(path=""):
    static_file_path = os.path.join(app.static_folder, path)
    if path != "" and os.path.exists(static_file_path):
        # prevent directory traversal
        if os.path.abspath(static_file_path).startswith(os.path.abspath(app.static_folder)):
            return send_from_directory(app.static_folder, path), 200
        else:
            # path is outside the static folder, deny access
            return "Not Found", 404
    else:
        # for acceptable paths, serve the entry point
        return send_from_directory(BUILD_DIR, 'index.html'), 200




# actual python script execution starts here
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print("Flask server starting...")
    print(f"Serving frontend from: {BUILD_DIR}")
    print(f"Static folder set to: {app.static_folder}")
    print(f"Listening on http://localhost:{port}")
    # run the flask server on the host="0.0.0.0" which lets the server be seen externally
    # port is the determiner for where on the network it is accessible
    
    # initialize dex auth users into database
    print(f"Initializing dex authorized users into the database...")
    initialize_users()
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)  # set threaded = true for multiple requests at once