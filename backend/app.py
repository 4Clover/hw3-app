import time

from bson import ObjectId
from flask import Flask, jsonify, send_from_directory, request, redirect, session
import os, requests
from flask_cors import CORS
from pymongo import MongoClient, DESCENDING
from authlib.common.security import generate_token
from authlib.integrations.flask_client import OAuth
from functools import wraps


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
REGISTERED_OIDC_CLIENT_NAME = os.getenv('OIDC_CLIENT_NAME', 'NAME_NOT_SET')
if REGISTERED_OIDC_CLIENT_NAME == 'NAME_NOT_SET':
    app.logger.warning(
        "OIDC_CLIENT_NAME env var not set, using default. ISSUES INBOUND.")
elif not REGISTERED_OIDC_CLIENT_NAME.isidentifier():
    app.logger.error(
        # we love good logging messages, right?
        f"OIDC_CLIENT_NAME ('{REGISTERED_OIDC_CLIENT_NAME}') is not a valid Python identifier. Authlib client access will fail. Please fix in .env.dev.")
    raise ValueError(f"OIDC_CLIENT_NAME ('{REGISTERED_OIDC_CLIENT_NAME}') must be a valid Python identifier.")




nonce = generate_token()

# ---------- DEX SET UP  ----------
oauth.register(
    name=REGISTERED_OIDC_CLIENT_NAME,
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

# ---------- HELPER FUNCTIONS ----------

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

@app.route('/api/me')
def current_user_api():
    user_session_data = session.get('user')
    app.logger.info(f"[/api/me] User session data from session: {user_session_data}")

    if user_session_data:
        user_id_for_check = user_session_data.get('userID')
        username_for_check = user_session_data.get('username')

        role = "user" # default role
        # role checking
        if str(user_id_for_check) == '123': # dex user id for admin
            role = "admin"
            app.logger.info(f"[/api/me] User ID '{user_id_for_check}' matches ADMIN_ID '123'. Role set to 'admin'.")
        elif str(user_id_for_check) == '456': # dex user id for moderator
            role = "moderator"
            app.logger.info(f"[/api/me] User ID '{user_id_for_check}' matches MODERATOR_ID '456'. Role set to 'moderator'.")
        elif username_for_check == 'admin' and role == 'user':
            role = "admin"
            app.logger.info(f"[/api/me] Username '{username_for_check}' matches 'admin'. Role set to 'admin'.")
        elif username_for_check == 'moderator' and role == 'user':
            role = "moderator"
            app.logger.info(f"[/api/me] Username '{username_for_check}' matches 'moderator'. Role set to 'moderator'.")


        app.logger.info(f"[/api/me] Final determined role: '{role}' for userID: '{user_id_for_check}', username: '{username_for_check}'")

        return jsonify({
            "loggedIn": True,
            "email": user_session_data.get('email'),
            "username": username_for_check,
            "userID": user_id_for_check,
            "role": role
        }), 200

    return jsonify({"loggedIn": False}), 200


def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_session_data = session.get('user')
            app.logger.info(f"[role_required] User session data: {user_session_data}")

            if not user_session_data:
                return jsonify({"error": "Authentication required"}), 401

            user_id_for_check = user_session_data.get('userID')
            username_for_check = user_session_data.get('username')

            user_role = "user" # default role
            if str(user_id_for_check) == '123':
                user_role = "admin"
            elif str(user_id_for_check) == '456':
                user_role = "moderator"
            elif username_for_check == 'admin' and user_role == 'user':
                user_role = "admin"
            elif username_for_check == 'moderator' and user_role == 'user':
                user_role = "moderator"

            app.logger.info(f"[role_required] Determined role: '{user_role}' for userID: '{user_id_for_check}', username: '{username_for_check}'. Allowed: {allowed_roles}")

            if user_role not in allowed_roles:
                return jsonify({"error": "Forbidden: Insufficient privileges"}), 403

            kwargs['moderator_info'] = user_session_data
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.route('/api/login')
def login():
    current_nonce = generate_token()
    session['nonce'] = current_nonce
    redirect_uri = 'http://localhost:8000/api/authorize'

    try:
        oauth_client = getattr(oauth, REGISTERED_OIDC_CLIENT_NAME)
        return oauth_client.authorize_redirect(redirect_uri, nonce=current_nonce)
    except AttributeError:
        app.logger.error(f"Authlib client '{REGISTERED_OIDC_CLIENT_NAME}' not found.")
        return "OAuth client configuration error (login).", 500
    except Exception as e:
        app.logger.error(f"Unexpected error during authorize_redirect for {REGISTERED_OIDC_CLIENT_NAME}: {e}", exc_info=True)
        # check dex logs if this errors
        return "OAuth initiation error.", 500

@app.route('/api/authorize')
def authorize():
    if not REGISTERED_OIDC_CLIENT_NAME: # env load check
        app.logger.error("OIDC client name not available during /api/authorize.")
        return "OAuth client configuration error (authorize: name missing).", 500
    try:
        oauth_client = getattr(oauth, REGISTERED_OIDC_CLIENT_NAME)
        token = oauth_client.authorize_access_token()
    except AttributeError:
        app.logger.error(f"Authlib client '{REGISTERED_OIDC_CLIENT_NAME}' not found on oauth object during authorize_access_token. Check registration name.")
        return "OAuth client configuration error (authorize: client not found).", 500
    except Exception as e:
        app.logger.error(f"Error during authorize_access_token for '{REGISTERED_OIDC_CLIENT_NAME}': {e}", exc_info=True)
        # check dex logs if this errors
        return "Error obtaining access token from provider.", 500

    retrieved_nonce = session.pop('nonce', None) # get and remove nonce
    if not retrieved_nonce:
        app.logger.warning("Nonce not found in session during /api/authorize callback. This could be a security risk or indicate a flow issue.")

    try:
        user_info = oauth_client.parse_id_token(token, nonce=retrieved_nonce)
        # `token` is the dictionary containing id_token, access_token, etc.
        # parse_id_token = token['id_token']
    except Exception as e:
        app.logger.error(f"Error parsing ID token or invalid nonce for client '{REGISTERED_OIDC_CLIENT_NAME}': {e}", exc_info=True)
        return "Invalid token or authentication session.", 400 # bad req or unauthorized

    try:
        oauth_client = getattr(oauth, REGISTERED_OIDC_CLIENT_NAME)
        parsed_claims = oauth_client.parse_id_token(token, nonce=retrieved_nonce) # dict of claims
        app.logger.info(f"[/api/authorize] Parsed ID token claims from Authlib: {parsed_claims}")

        dex_user_id = parsed_claims.get('sub') # subject claim
        dex_email = parsed_claims.get('email') # should be admin@hw3.com, etc.

        authlib_username_claim = parsed_claims.get('username') # what authlib maps
        dex_internal_username_log = "admin"

        session_user_data = {
            'email': dex_email,
            'userID': dex_user_id,
            'username': parsed_claims.get('name') or authlib_username_claim or dex_email.split('@')[0], # fallback chain
            'raw_claims': parsed_claims # store all claims for debugging
        }

        app.logger.info(f"[/api/authorize] Data to be stored in session['user']: {session_user_data}")
        session['user'] = session_user_data

        if users_collection is not None and session_user_data.get('userID'):
            users_collection.update_one(
                {'dex_user_id': session_user_data['userID']},
                {'$set': {
                    'email': session_user_data.get('email'),
                    'username': session_user_data.get('username'), # display name
                    'last_login': time.time()
                }},
                upsert=True
            )
        else:
            app.logger.warning(f"[/api/authorize] userID not found in session_user_data or users_collection is None. User DB update skipped. session_user_data: {session_user_data}")


        return redirect('http://localhost:5173/') # svelte

    except Exception as e:
        app.logger.error(f"Error during authorize_access_token or parsing for '{REGISTERED_OIDC_CLIENT_NAME}': {e}", exc_info=True)
        return "Error processing authentication.", 500

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
        if not data or 'content' not in data or 'articleId' not in data:
            return jsonify({"error": "Missing articleId or content in request"}), 400

        user_session_info = session.get('user')
        author_name = "TEMP - Anon" # default if not logged in or no username
        if user_session_info:
            # p]refer username from Dex staticPasswords, fallback to email
            author_name = user_session_info.get('username', user_session_info.get('email', "TEMP - Anon"))

        comment_doc = {
            "articleId": str(data["articleId"]), # str cast to ensure consistency
            "author": author_name,
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
        "author": comment_doc.get("author", "Anonymous"),
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

# ----------------- MODERATION ENDPOINTS ------------------
@app.route("/api/comments/<comment_id>/moderate", methods=["PUT"])
@role_required(["admin", "moderator"]) # Protect this endpoint
def moderate_comment(comment_id, moderator_info): # moderator_info injected by decorator
    if comments_collection is None:
        return jsonify({"error": "Database service not available"}), 503

    if not ObjectId.is_valid(comment_id):
        return jsonify({"error": "Invalid comment ID format"}), 400

    data = request.get_json()
    if not data or "action" not in data:
        return jsonify({"error": "Missing 'action' in request body (e.g., 'delete_full', 'redact_partial')"}), 400

    action = data.get("action")
    moderator_name = moderator_info.get('username', moderator_info.get('email', "Unknown Moderator"))

    update_fields = {
        "removed": True,
        "removedBy": moderator_name,
        "moderationTimestamp": time.time()
    }

    if action == "delete_full":
        update_fields["content"] = "Comment has been deleted by moderation."
    elif action == "redact_partial":
        new_content = data.get("new_content")
        if new_content is None: # Check for None, empty string might be valid for full clear by mistake
            return jsonify({"error": "Missing 'new_content' for redaction"}), 400
        update_fields["content"] = new_content # frontend sends the block characters
    else:
        return jsonify({"error": f"Invalid moderation action: {action}"}), 400

    try:
        result = comments_collection.update_one(
            {"_id": ObjectId(comment_id)},
            {"$set": update_fields}
        )

        if result.matched_count == 0:
            return jsonify({"error": "Comment not found"}), 404

        if result.modified_count == 0 and result.matched_count > 0:
            # comment was already in target state
            app.logger.info(f"Comment {comment_id} was matched but not modified by moderation. State might have been identical.")


        # fetch updated comment
        updated_comment_doc = comments_collection.find_one({"_id": ObjectId(comment_id)})
        if not updated_comment_doc:
            # if matched_count > 0 will not happen
            return jsonify({"error": "Failed to retrieve comment after moderation"}), 500

        return jsonify(serialize_comment_for_frontend(updated_comment_doc)), 200

    except Exception as e:
        app.logger.error(f"Error moderating comment {comment_id}: {e}", exc_info=True)
        return jsonify({"error": f"Internal server error during moderation: {str(e)}"}), 500



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