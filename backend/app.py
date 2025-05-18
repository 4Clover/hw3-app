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
# removed previous constants as not in use
BASE_NYT_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

# flask app init, serves all static files from the build directory to the frontend
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
    app.logger.info(f"Connected to MongoDB! Database: {db.name}. Comments collection ready.")
    # adding users collection to keep track of users in database
    users_collection = db["users"]
    app.logger.info(f"Database {db.name} successfully created collection: users!")
except Exception as e:
    app.logger.error(f"Error connecting to MongoDB or comments collection: {e}")

# removed serializer as Mongo has internal function for this

def get_key():
    api_key = os.getenv("NYT_API_KEY")
    # check for if not set or template placeholder is present
    if not api_key or api_key == "super_secret_key":
        app.logger.error("NYT_API_KEY environment variable not set or is placeholder.")
        return None
    return api_key

# ------------ DEX API ENDPOINTS ---------------
@app.route('/')
def get_user():
    user = session.get('user')
    if user:
        return {user['email']}
    return f"No user found."

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
        # author is no longer sent from frontend, will be "TEMP - Anon" until TODO: Dex OAuth
        if not data or 'content' not in data or 'articleId' not in data:
            return jsonify({"error": "Missing articleId or content in request"}), 400

        comment_doc = {
            "articleId": str(data["articleId"]), # str cast to ensure consistency
            "author": "TEMP - Anon", # TODO: Dex OAuth
            "content": data["content"],
            "timestamp": time.time(),  # UNIX timestamp (float)
            "removed": False,
            "removedBy": "",
            "parentId": data.get("parentId") # parentId for replies, None if not present
        }

        # confirm parent exists
        if comment_doc["parentId"] is not None:
            try:
                # object ID generated via Mongo
                ObjectId(comment_doc["parentId"]) # already a string from data.get()
            except Exception as error:
                app.logger.warning(f"Invalid parentId format: {comment_doc['parentId']}. Storing as null.", error)
                comment_doc["parentId"] = None


        result = comments_collection.insert_one(comment_doc)

        # new comment in frontend structure
        created_comment_response = {
            "id": str(result.inserted_id),
            "articleId": comment_doc["articleId"],
            "author": comment_doc["author"],
            "content": comment_doc["content"],
            "removed": comment_doc["removed"],
            "removedBy": comment_doc["removedBy"],
            "timestamp": comment_doc["timestamp"],
            "parentId": comment_doc["parentId"] # string or None
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
        "author": comment_doc.get("author", "TEMP - Anon"), # TODO: Dex OAuth
        "content": comment_doc.get("content", ""),
        "removed": comment_doc.get("removed", False),
        "removedBy": comment_doc.get("removedBy", ""),
        "timestamp": comment_doc.get("timestamp"),
        "parentId": str(comment_doc["parentId"]) if comment_doc.get("parentId") else None # type check again, I think unneeded but safe to keep
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
def get_comment_by_id(comment_id):
    if comments_collection is None:
        return jsonify({"error": "Database service not available"}), 503
    try:
        # validate comment_id format before query
        if not ObjectId.is_valid(comment_id):
            return jsonify({"error": "Invalid comment ID format"}), 400
        comment = comments_collection.find_one({"_id": ObjectId(comment_id)})
        if comment:
            return jsonify(serialize_comment_for_frontend(comment)), 200
        else:
            return jsonify({"error": "Comment not found"}), 404
    except Exception as error: # broad catch, need specific for ID errors
        app.logger.error(f"Error fetching comment by ID '{comment_id}': {error}", exc_info=True)
        return jsonify({"error": f"Internal server error: {str(error)}"}), 500

# TODO: Add moderator change, delete, and update endpoints
# Redacted text per HW should be replaced with Unicode character 'FULL BLOCK' (U+2588) -- possibly done via frontend?

# removed Alyssa code so future tests use current implementations

# article testing endpoint
@app.route("/api/test_articles") # temp -- will delete at some point
def get_articles():
    try:
        # placeholder data - replace this with actual NYT API calls
        # added articleUrl to match frontend
        placeholder_articles = [
            {"id": "nyt1", "headline": "Breaking: Lime Shortage Sparks Citrus Panic", "imageUrl": "/images/1.png", "author": "Zesty Lemonsworth", "content": "Citizens storm supermarkets...", "articleUrl": "#nyt1"},
            {"id": "nyt2", "headline": "Exclusive Interview: \"Life as a Lime Farmer\"", "imageUrl": "/images/2.png", "author": "Margarita Limeberg", "content": "Farmer Zest McJuicy reveals secrets...", "articleUrl": "#nyt2"},
            {"id": "nyt3", "headline": "Opinion: Is Lime the New Lemon?", "imageUrl": "/images/3.png", "author": "Citrus McPeel", "content": "Lemon lobbyists are furious...", "articleUrl": "#nyt3"},
            {"id": "nyt4", "headline": "Study Reveals 9 Out of 10 Doctors Recommend More Limes", "imageUrl": "/images/5.png", "author": "Dr. Key Limeman", "content": "'Sourness improves your mood,' scientists confirm...", "articleUrl": "#nyt4"},
            {"id": "nyt5", "headline": "Sports Update: Limetown Limers Win the Citrus Cup", "imageUrl": "/images/6.png", "author": "Coach Ricky Rind", "content": "Fans chant, 'When life gives you limes...'", "articleUrl": "#nyt5"},
            {"id": "nyt6", "headline": "Technology Breakthrough: Smartphone Now Charges Using Limes", "imageUrl": "/images/7.png", "author": "Elon Zest", "content": "Tech company CEO proudly announces...", "articleUrl": "#nyt6"},
            {"id": "nyt7", "headline": "Travel Guide: Top 5 Lime-Themed Destinations", "imageUrl": "/images/1.png", "author": "Clementine Sourwood", "content": "Visit Lime Island, Limetown...", "articleUrl": "#nyt7"},
            {"id": "nyt8", "headline": "Economics: LimeCoin Cryptocurrency Hits Record High", "imageUrl": "/images/8.png", "author": "Warren Zuffet", "content": "Investors advise: 'Buy low, zest high.'", "articleUrl": "#nyt8"},
            {"id": "nyt9", "headline": "Cooking Tips: How to Lime Your Way to Culinary Stardom", "imageUrl": "/images/9.png", "author": "Chef Zestina Peelini", "content": "'A lime a day keeps blandness away,' celebrity chef advises.", "articleUrl": "#nyt9"},
            {"id": "nyt10", "headline": "Crime Report: Lime Bandits Strike Again", "imageUrl": "/images/1.png", "author": "Detective Perry Limecroft", "content": "Thieves apprehended after stealing 1,000 limes...", "articleUrl": "#nyt10"},
            {"id": "nyt11", "headline": "Weather Forecast: Heavy Lime Showers Expected", "imageUrl": "/images/12.png", "author": "Sunny Citrina", "content": "Meteorologists warn residents to carry cocktail umbrellas...", "articleUrl": "#nyt11"},
            {"id": "nyt12", "headline": "Science: Lime Juice Found on Mars", "imageUrl": "/images/10.png", "author": "Neil Zestrong", "content": "NASA confirms, 'The red planet is now officially zesty.'", "articleUrl": "#nyt12"}
        ]
        return jsonify(placeholder_articles)
    except Exception as e:
        app.logger.error(f"Error fetching placeholder articles: {e}")
        return jsonify({"error": "Failed to load articles"}), 500

# parse API data into dictionary for frontend
def parse_article_data(article_doc): # renamed 'article' to 'article_doc' to avoid conflict with 'article' module
    try:
        headline_obj = article_doc.get('headline', {}) # headline dict
        main_headline = headline_obj.get('main', 'No Headline Available') # string
        byline_obj = article_doc.get('byline', {}) # byline dict
        original_byline = byline_obj.get('original', '') # string
        author = original_byline.removeprefix('By ').strip() if original_byline else 'Unknown Author' # strip 'By' if on author
        content_summary = article_doc.get('abstract', article_doc.get('snippet', 'No summary available')) # option for if the abstract is not available, but likely never to be used
        multimedia = article_doc.get('multimedia')
        # aria image text here?
        article_id = article_doc.get('_id', None)
        web_url = article_doc.get('web_url', '#') # fallback to '#'
        image_url = multimedia.get('default').get('url')

        # article_id required for column population on frontend
        if not article_id:
            app.logger.error(f"Article missing _id: {article_doc}")
            return None # skip if no ID

        return { # dictionary
            'id': article_id,
            'headline': main_headline,
            'author': author,
            'content': content_summary,
            'imageUrl': image_url, # none if no image found
            'articleUrl': web_url
        }
    except Exception as e:
        # includes exc for ease of debugging
        app.logger.error(f"Error parsing article data for article ID {article_doc.get('_id', 'N/A')}: {e}", exc_info=True)
        return None

@app.route("/api/search")
def fetch_nyt_articles():
    api_key = get_key()
    if not api_key:
        # send error to frontend to show on webpage
        return jsonify({"error": "Server error: NYT API key not set."}), 500

    processed_articles = []

    search_query = request.args.get('query')
    # Removed the strict validation for search_query to allow more flexibility,
    # but you might want to add some basic sanitization or validation.
    # if search_query not in ['davis', 'sacramento', ...]: # Your original check
    #     return jsonify({"error": f"Invalid search query: {search_query}. Please try again later."}), 400

    search_begin_date = request.args.get('begin_date')
    search_end_date = request.args.get('end_date')
    search_filter = request.args.get('filter') # None most of the time
    search_page = request.args.get('page', default=0, type=int)

    # debug info for reference, check vite.config.ts for what is actually being sent
    app.logger.info(f"NYT API Search - Query:'{search_query}', BeginDate:'{search_begin_date}', EndDate:'{search_end_date}', Filter:'{search_filter}', Page:'{search_page}'")

    params = { 'api-key': api_key, 'page': search_page }
    if search_query: params['q'] = search_query
    if search_begin_date: params['begin_date'] = search_begin_date # format YYYYMMDD
    if search_end_date: params['end_date'] = search_end_date     # format YYYYMMDD
    if search_filter: params['fq'] = search_filter # add fq as a param if it actually has something

    try:
        nyt_req = requests.get(BASE_NYT_URL, params=params)
        nyt_req.raise_for_status() # check for an HTTP error (4xx or 5xx)
        nyt_data = nyt_req.json()

        # structure check
        if 'response' not in nyt_data or 'docs' not in nyt_data['response']:
            app.logger.error(f"Unexpected NYT API response structure for query '{search_query}': {nyt_data}")
            return jsonify({"error": "Malformed response from NYT API."}), 502 # Bad Gateway or similar error

        articles_list = nyt_data['response']['docs'] # error check on data structure can go here

        for indiv_article in articles_list: # Renamed 'article' to 'article_item'
            # type check before parse
            if isinstance(indiv_article, dict) :
                parsed_article = parse_article_data(indiv_article)
                if parsed_article:
                    processed_articles.append(parsed_article)
            else :
                app.logger.warning(f"Article item is not a dict - skipped: {indiv_article}")

        return jsonify(processed_articles)

    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error occurred while fetching NYT articles: {http_err}."
        try: # try to get more specific error from NYT response if available
            error_detail_json = nyt_req.json()
            if "fault" in error_detail_json and "faultstring" in error_detail_json["fault"]:
                error_message += f" Detail: {error_detail_json['fault']['faultstring']}"
            elif "message" in error_detail_json:
                error_message += f" Detail: {error_detail_json['message']}"

        except ValueError: # if not JSON
            error_message += f" Response: {nyt_req.text[:200]}" # log snippet of non-JSON response

        app.logger.error(error_message)
        return jsonify({"error": "Failed to retrieve articles from NYT."}), nyt_req.status_code if nyt_req else 500
    except Exception as e:
        app.logger.error(f"An unexpected error occurred while fetching NYT articles: {e}", exc_info=True)
        return jsonify({"error": "An unexpected server error occurred. Please try again later."}), 500


@app.route("/test/test-mongo")
def test_mongo_connection():
    if not client: # check if client exists
        return jsonify({"error": "MongoDB client not initialized"}), 503
    try:
        server_info = client.server_info() # "pings" the server
        return jsonify({
            "message": "Successfully connected to MongoDB!",
            "server_version": server_info.get('version'),
            # must be None comparison as Mongo object isn't truth/falsy
            "collections": db.list_collection_names() if db is not None else "Database not initialized"
        })
    except Exception as e:
        app.logger.error(f"MongoDB connection test failed: {e}", exc_info=True) # exc_info for debug
        return jsonify({"error": f"MongoDB connection test failed: {str(e)}"}), 500

# serve frontend HTML (svelte)
@app.route("/")
@app.route("/<path:path>")
def serve_frontend(path=""):
    # serves static files from the 'static_folder' (BUILD_DIR/static for svelte typically)
    # or the index.html from BUILD_DIR for the root path or unknown paths.
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        # prevent directory traversal
        safe_path = os.path.join(app.static_folder, path)
        if os.path.abspath(safe_path).startswith(os.path.abspath(app.static_folder)):
            return send_from_directory(app.static_folder, path), 200
        else:
            # path is outside the static folder, deny access
            app.logger.warning(f"Attempted directory traversal: {path}")
            return "Not Found", 403 # changed to 403: forbidden
    else:
        # for acceptable paths, serve the entry point (index.html)
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
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    # set threaded = true for multiple requests at once
    app.run(host="0.0.0.0", port=port, debug=debug_mode, threaded=True)