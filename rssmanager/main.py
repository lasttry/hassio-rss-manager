import json
import os
import logging
import uuid
from flask import Flask, jsonify, render_template, request, Response
import requests
from io import BytesIO
from PIL import Image
import base64
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from lxml import etree

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    static_folder="ui",
    static_url_path="",
    template_folder="ui"
)

OPTIONS_FILE = "/data/options.json"
DEV_OPTIONS_FILE = "data/options.json"
DATA_FILE = "/data/rss_items.json"
DB_PATH = "/data/rss.db"
DEV_DB_PATH = "data/rsss.db"
VERSION = ""
TORRENTURL = ""
TORRENTUSER = ""
TORRENTPASS = ""
OMDBAPIKEY = "24399217"

APIKey = "c26f3f9d62b05bc814020aff6928dcf6"
APIReadAccessToken = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjMjZmM2Y5ZDYyYjA1YmM4MTQwMjBhZmY2OTI4ZGNmNiIsIm5iZiI6MTc1NjY0MjAyNC45MDcsInN1YiI6IjY4YjQzYWU4OTkxNDg5OGZkNTM5N2U4MyIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.6cLPBhwIP_eJBJ948i5fYyVXIhTIj2-eKCAg3TCphuQ"

NAMESPACES = {"torznab": "http://torznab.com/schemas/2015/feed"}

def load_options():
    path = OPTIONS_FILE if os.path.exists(OPTIONS_FILE) else DEV_OPTIONS_FILE
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not load options from {path}: {e}")
        return {}

options = load_options()
DEBUG = options.get("debug", False)
TORRENTURL = options.get("torrentURL", 'http://llfe01:8080')
TORRENTUSER = options.get("torrentUser")
TORRENTPASS = options.get("torrentPass")
raw_feeds = options.get("feeds", [])
FEEDS = {}

for feed in raw_feeds:
    name = feed.get("name")
    url = feed.get("url")
    if name and url:
        FEEDS[name] = url
    else:
        logging.warning(f"Ignoring feed with missing name or url: {feed}")

logging.basicConfig(
    level=logging.DEBUG if DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info(f"RSS Manager running in version: {VERSION}")
logging.info(f"Debug mode is {'enabled' if DEBUG else 'disabled'}")

# Aqui termina a parte 1, vamos continuar na próxima célula.

@contextmanager
def open_db():
    path = DB_PATH if os.path.exists(DB_PATH) else DEV_DB_PATH
    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            feed TEXT,
            title TEXT,
            link TEXT,
            guid TEXT,
            cover_url TEXT,
            poster_b64 TEXT,
            description TEXT,
            status TEXT DEFAULT 'new',
            attrs TEXT
        )
        """)
        conn.commit()

def save_item(item):
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO items (id, feed, title, link, guid, cover_url, poster_b64, description, status, attrs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item["id"],
            item["feed"],
            item["title"],
            item["link"],
            item["guid"],
            item.get("coverUrl"),
            item.get("poster_b64"),
            item.get("description"),
            item.get("status", "new"),
            json.dumps(item.get("attrs", {}))
        ))
        conn.commit()

def save_items(items: list[dict]) -> int:
    """Bulk insert or replace a list of items into the DB."""
    for item in items:
        save_item(item)

def delete_items(feed):
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM items
            WHERE feed = ?
        """, (feed,))  # ⚠️ Atenção à vírgula: (feed,) é um tuple de 1 elemento
        deleted = cursor.rowcount
        conn.commit()
        return deleted

def get_item(id):
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM items
            WHERE id = ?
        """, (id,))  # tuple com 1 elemento
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

def get_all_items():
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id,
                feed,
                title,
                link,
                guid,
                cover_url,
                description,
                status,
                attrs,
                CASE
                    WHEN poster_b64 IS NOT NULL AND LENGTH(poster_b64) > 0 THEN 1
                    ELSE 0
                END AS has_image
            FROM items
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

def update_item_status(item_id, status="hidden"):
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE items SET status=? WHERE id=?", (status, item_id))
        conn.commit()

def update_item_sent(item_id, status, sentAt):
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE items SET
                status=?
                sentAt=?
            WHERE id=?
        """, (status, sentAt, id,))
        conn.commit()

def get_visible_items():
    all_items = get_all_items()
    return [
        item for item in all_items
        if item.get("status") != "sent" and item.get("status") != "hidden"
    ]

def get_existing_keys():
    """Returns a set of keys: guid or 'title_feed' fallback"""
    with open_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT guid, title, feed FROM items")
        rows = cursor.fetchall()
        return {
            row[0] if row[0] else f"{row[1]}_{row[2]}"
            for row in rows
        }

def get_poster_image(imdbid):
    try:
        logging.info(f"Getting info from {imdbid}")
        if not imdbid or imdbid.strip().lower() == 'null':
            return None, None

        r = requests.get(f"http://www.omdbapi.com/?i={imdbid}&apikey={OMDBAPIKEY}")
        data = r.json()
        if "Poster" not in data or data["Poster"] == "N/A":
            return None, None

        image_url = data["Poster"]
        plot = data.get("Plot", "")

        img_resp = requests.get(image_url)
        img = Image.open(BytesIO(img_resp.content)).convert("RGB")
        img = img.resize((300, 300))

        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=80)
        img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        print(f"base64img: {img_base64}")
        return img_base64, plot  # ✅ BASE64 STRING
    except Exception as e:
        logging.warning(f"❌ IMDb metadata error: {e}")
        return None, None

def update_feeds():
    existing_keys = get_existing_keys()
    new_items = []

    for feed_name, url in FEEDS.items():
        logging.debug(f"🔁 Fetching feed: {feed_name} from {url}")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except Exception as e:
            logging.warning(f"⚠️ Failed to fetch feed {feed_name}: {e}")
            continue

        try:
            parser = etree.XMLParser(recover=True)
            tree = etree.parse(BytesIO(response.content), parser)
            root = tree.getroot()

            for item in root.xpath("//item"):
                title_elem = item.find("title")
                link_elem = item.find("link")
                guid_elem = item.find("guid")

                title = title_elem.text.strip() if title_elem is not None else None
                link = link_elem.text.strip() if link_elem is not None else None
                guid = guid_elem.text.strip() if guid_elem is not None else None
                key = guid if guid else f"{title}_{feed_name}"

                if not title or not link:
                    continue
                if key in existing_keys:
                    continue

                # Optional: parse torznab:attr tags
                attrs = {}
                for attr in item.xpath("torznab:attr", namespaces=NAMESPACES):
                    name = attr.get("name")
                    value = attr.get("value")
                    if name and value:
                        attrs[name] = value

                logging.debug(f"🎯 New item: {title}")
                if attrs:
                    logging.debug(f"    ↪ Attributes: {attrs}")

                poster_b64, description = get_poster_image(attrs.get("imdbid"))
                poster_url = attrs.get("coverurl")
                new_items.append({
                    "id": str(uuid.uuid4()),
                    "feed": feed_name,
                    "title": title,
                    "link": link,
                    "guid": guid,
                    "coverUrl": poster_url,
                    "status": "new",
                    "attrs": attrs,
                    "poster_b64": poster_b64,
                    "description": description
                })
                logging.info(f"✅ New item added: {title} ({feed_name})")

        except Exception as e:
            logging.error(f"❌ Failed to parse XML for feed {feed_name}: {e}")

    save_items(new_items)
    logging.info(f"✅ Feeds updated. {len(new_items)} new items.")
    return get_visible_items()

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

@app.route("/rss/poster/<item_id>")
def get_poster(item_id):
    item = get_item(item_id)
    if not item or not item.get("poster_b64"):
        return "", 404
    img_data = base64.b64decode(item["poster_b64"])
    logging.debug(img_data)
    return Response(f"data:image/jpeg;base64,{img_data}", mimetype="image/jpeg")

@app.route("/rss/update", methods=["POST"])
def manual_update():
    logging.debug("POST /rss/update called")
    updated = update_feeds()
    return jsonify({"count": len(updated)})

@app.route("/rss/send/<item_id>", methods=["POST"])
def send_item(item_id):
    target = get_item(item_id)

    if not target:
        return jsonify({"success": False, "error": "Item not found"}), 404

    try:
        send_to_qbittorrent(target)
        update_item_sent(target["id"], "sent", datetime.now().isoformat())
        logging.info(f"Item {item_id} sent to qBittorrent")
        return jsonify({"success": True, "id": item_id})
    except Exception as e:
        logging.error(f"Error sending item {item_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/rss", methods=["GET"])
def get_rss():
    items = get_visible_items()
    return jsonify({"feed_items": items})

@app.route("/rss/hide/<item_id>", methods=["POST"])
def hide_item(item_id):
    update_item_status(item_id, "hidden")
    return jsonify({"success": True, "id": item_id})

@app.route("/rss/<feed_name>", methods=["DELETE"])
def delete_feed_items(feed_name):
    deleted_count = delete_items(feed_name)

    logging.info(f"Deleted {deleted_count} items from feed '{feed_name}'")
    return jsonify({
        "message": f"Deleted {deleted_count} items from feed '{feed_name}'",
        "deleted": deleted_count
    }), 200


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

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4567)
