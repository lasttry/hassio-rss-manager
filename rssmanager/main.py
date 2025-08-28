import feedparser
import json
import os
import uuid
import logging
from flask import Flask, jsonify, request, send_from_directory, render_template
import requests
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    static_folder="ui",         # Serve ficheiros estáticos a partir da pasta ui/
    static_url_path="",         # Faz com que /app.js vá diretamente a essa pasta
    template_folder="ui"        # Usa index.html dessa pasta também
)

OPTIONS_FILE = "/data/options.json"
DEV_OPTIONS_FILE = "data/options.json"
DATA_FILE = "/data/rss_items.json"
VERSION = ""
TORRENTURL = ""
TORRENTUSER = ""
TORRENTPASS = ""

# Load options (either from Hass.io or dev file)
def load_options():
    path = OPTIONS_FILE if os.path.exists(OPTIONS_FILE) else DEV_OPTIONS_FILE
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not load options from {path}: {e}")
        return {}
# Setup logging
options = load_options()
DEBUG = options.get("debug", False)
TORRENTURL = options.get("torrentURL", 'http://llfe01:8080')
TORRENTUSER = options.get("torrentUser")
TORRENTPASS = options.get("torrentPass")

# --- Setup Logging ---
logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info(f"RSS Manager running in version: {VERSION}")
logging.info(f"Debug mode is {'enabled' if DEBUG else 'disabled'}")

# --- Feed Sources ---
FEEDS = {
    "showrss": "https://showrss.info/user/291413.rss?magnets=true&namespaces=true&name=null&quality=null&re=null",
    "yts": "http://llfe01:9117/api/v2.0/indexers/yts/results/torznab/api?apikey=fxyo4pol1ofadbat6tuu44nc49vs5d98&t=search&cat=&q="
}

# --- Load stored items ---
def load_items():
    if not os.path.exists(DATA_FILE):
        logging.info("No previous rss_items.json found. Starting fresh.")
        return []
    try:
        with open(DATA_FILE, "r") as f:
            items = json.load(f)
            logging.info(f"Loaded {len(items)} existing RSS items.")
            return items
    except Exception as e:
        logging.error(f"Failed to load items from file: {e}")
        return []

# --- Save items back to file ---
def save_items(items):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(items, f, indent=2)
        logging.info(f"Saved {len(items)} total items to {DATA_FILE}")
    except Exception as e:
        logging.error(f"Failed to save items: {e}")

# --- Update all feeds ---

def update_feeds():
    existing = load_items()
    existing_keys = {item.get("guid", f"{item['title']}_{item['feed']}") for item in existing}
    new_items = []

    for feed_name, url in FEEDS.items():
        logging.debug(f"Fetching feed: {feed_name} from {url}")
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            guid = entry.get("guid", None)
            key = guid if guid else f"{entry.title}_{feed_name}"

            if key in existing_keys:
                continue

            new_items.append({
                "id": str(uuid.uuid4()),           # GUID interno
                "feed": feed_name,
                "title": entry.title,
                "link": entry.link,
                "guid": guid,
                "status": "new",
            })
            logging.info(f"New item added: {entry.title} ({feed_name})")

    all_items = new_items + existing
    save_items(all_items)
    logging.info(f"Feeds updated. {len(new_items)} new items.")
    return all_items

# --- API endpoints ---
@app.route("/rss", methods=["GET"])
def get_rss():
    logging.debug("GET /rss called")
    all_items = load_items()

    visible_items = [
        item for item in all_items
        if item.get("visible", True) and item.get("status") != "sent" and item.get("status") != "hidden"
    ]

    logging.debug(f"Returning {len(visible_items)} visible feed items")
    return jsonify({"feed_items": visible_items})

@app.route("/rss/update", methods=["POST"])
def manual_update():
    logging.debug("POST /rss/update called")
    updated = update_feeds()
    return jsonify({"count": len(updated)})

@app.route("/rss/hide/<item_id>", methods=["POST"])
def hide_item(item_id):
    items = load_items()
    updated = False

    for item in items:
        if item.get("id") == item_id:
            item["status"] = "hidden"
            updated = True
            logging.info(f"Item {item_id} marked as hidden")
            break

    if updated:
        save_items(items)
        return jsonify({"success": True, "id": item_id})
    else:
        logging.warning(f"Item {item_id} not found")
        return jsonify({"success": False, "error": "Item not found"}), 404


# --- SENDING to qbit --- #
def send_to_qbittorrent(item):

    if not TORRENTURL or not TORRENTUSER or not TORRENTPASS:
        raise Exception("Missing qBittorrent config in options.json")

    session = requests.Session()

    # Login
    login_url = f"{TORRENTURL}/api/v2/auth/login"
    r = session.post(login_url, data={"username": TORRENTUSER, "password": TORRENTPASS})
    if r.status_code != 200 or r.text != "Ok.":
        raise Exception("Failed to login to qBittorrent")

    # Add torrent
    add_url = f"{TORRENTURL}/api/v2/torrents/add"
    r = session.post(add_url, data={"urls": item["link"]})

    if r.status_code != 200:
        raise Exception("Failed to add torrent")

    return True

@app.route("/rss/send/<item_id>", methods=["POST"])
def send_item(item_id):
    items = load_items()
    target = next((i for i in items if i.get("id") == item_id), None)

    if not target:
        return jsonify({"success": False, "error": "Item not found"}), 404

    try:
        send_to_qbittorrent(target)
        target["status"] = "sent"
        target["sentAt"] = datetime.now().isoformat()
        save_items(items)
        logging.info(f"Item {item_id} sent to qBittorrent")
        return jsonify({"success": True, "id": item_id})
    except Exception as e:
        logging.error(f"Error sending item {item_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.errorhandler(404)
def handle_404(e):
    logging.warning(f"[404] Route not found: {str(e)} - {request.path}")
    return jsonify({"error": "Not Found", "path": request.path}), 404
@app.errorhandler(500)
def handle_500(e):
    logging.error(f"[500] Internal server error at: {request.path} - {str(e)}")
    return jsonify({"error": "Internal Server Error"}), 500

@app.route("/")
def index():
    return render_template("index.html")

# --- Start Flask ---
if __name__ == "__main__":
    logging.info("Initial feed update on startup...")
    update_feeds()
    app.run(host="0.0.0.0", port=4567)
