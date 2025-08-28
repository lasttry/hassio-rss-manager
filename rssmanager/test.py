
import requests
import xml.etree.ElementTree as ET

rss_url = "http://llfe01.diasantos.com:9117/api/v2.0/indexers/yts/results/torznab/api?apikey=fxyo4pol1ofadbat6tuu44nc49vs5d98&t=search"

response = requests.get(rss_url)
response.raise_for_status()

rss_content = response.text
root = ET.fromstring(rss_content)

namespaces = {
    "torznab": "http://torznab.com/schemas/2015/feed"
}

items = []
for item in root.findall(".//item"):
    title = item.findtext("title")
    link = item.findtext("link")
    coverurl = None

    for attr in item.findall("torznab:attr", namespaces=namespaces):
        if attr.attrib.get("name") == "coverurl":
            coverurl = attr.attrib.get("value")
            break

    items.append({
        "title": title,
        "link": link,
        "coverurl": coverurl
    })

print(f"{len(items)} items encontrados.\n")
for i in items[:5]:  # Mostra só os 5 primeiros
    print(i)
    