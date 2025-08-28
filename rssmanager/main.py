import json
import os
import logging
from flask import Flask, jsonify, render_template
import requests
from io import BytesIO
from PIL import Image
import base64
import sqlite3

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


def init_db():
    os.makedirs("/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

def save_item(item):
    conn = sqlite3.connect(DB_PATH)
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
    conn.close()

def get_all_items():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM items")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

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
        logging.info(f"Movie plot: {plot}")
        return f"data:image/jpeg;base64,{img_base64}", plot
    except Exception as e:
        logging.warning(f"❌ IMDb metadata error: {e}")
        return None, None


def update_item_status(item_id, status="hidden"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET status=? WHERE id=?", (status, item_id))
    conn.commit()
    conn.close()

def get_visible_items():
    all_items = get_all_items()
    return [
        item for item in all_items
        if item.get("status") != "sent" and item.get("status") != "hidden"
    ]

@app.route("/rss", methods=["GET"])
def get_rss():
    items = get_visible_items()
    return jsonify({"feed_items": items})

@app.route("/rss/hide/<item_id>", methods=["POST"])
def hide_item(item_id):
    update_item_status(item_id, "hidden")
    return jsonify({"success": True, "id": item_id})

@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4567)
