import requests
from bs4 import BeautifulSoup
import time
import sqlite3
from datetime import datetime
from typing import List, Dict, Any
import schedule
from pync import Notifier
from flask import Flask, render_template_string
import threading

# Configuration
DATABASE_NAME = 'chiikawa_items.db'
CHIIKAWA_URL = "https://chiikawamarket.jp/collections/newitems"
CHECK_INTERVAL_MINUTES = 5

app = Flask(__name__)

# Database Operations
def initialize_database() -> None:
    with sqlite3.connect(DATABASE_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS items
                     (name TEXT, photo_url TEXT, price TEXT, product_url TEXT, date_added TEXT)''')

def store_items(items: List[Dict[str, str]]) -> None:
    with sqlite3.connect(DATABASE_NAME) as conn:
        c = conn.cursor()
        for item in items:
            c.execute("INSERT INTO items (name, photo_url, price, product_url, date_added) VALUES (?, ?, ?, ?, ?)",
                      (item['name'], item['photo_url'], item['price'], item['product_url'], datetime.now().isoformat()))

def get_stored_items() -> List[Dict[str, str]]:
    with sqlite3.connect(DATABASE_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, photo_url, price, product_url FROM items")
        return [{'name': row[0], 'photo_url': row[1], 'price': row[2], 'product_url': row[3]} for row in c.fetchall()]

# Web Scraping
def fetch_website_content(url: str) -> str:
    response: requests.Response = requests.get(url)
    return response.text

def parse_items(html_content: str) -> List[Dict[str, str]]:
    soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')
    items: List[Any] = soup.find_all('div', class_='product--root')

    products: List[Dict[str, str]] = []
    for item in items:
        anchor_tag = item.find('a', href=True)
        product_url = f"https://chiikawamarket.jp{anchor_tag['href']}" if anchor_tag else ''

        img_tag = item.find('img', class_='lazyload')
        photo_url = img_tag['data-src'].replace('{width}', '1200') if img_tag and 'data-src' in img_tag.attrs else ''

        product: Dict[str, str] = {
            'name': item.find('h2', class_='product_name').text.strip(),
            'photo_url': photo_url,
            'price': item.find('div', class_='product_price').text.strip(),
            'product_url': product_url
        }
        products.append(product)

    return products

# Notification
def send_notification(new_items: List[Dict[str, str]]) -> None:
    print("New items found:")
    notification_text = "\n".join([f"{item['name']} - {item['price']}" for item in new_items])
    print(notification_text)

    Notifier.notify(
        message=notification_text,
        title="New Chiikawa Items!",
        open=CHIIKAWA_URL,
        sound='Blow'
    )

# Main Logic
def check_for_updates() -> None:
    html_content: str = fetch_website_content(CHIIKAWA_URL)
    current_items: List[Dict[str, str]] = parse_items(html_content)
    stored_items: List[Dict[str, str]] = get_stored_items()

    new_items: List[Dict[str, str]] = [item for item in current_items if item['product_url'] not in [stored_item['product_url'] for stored_item in stored_items]]

    if new_items:
        store_items(new_items)
        send_notification(new_items)
    else:
        print(f"No new items found at {datetime.now()}")

def job():
    print(f"Checking for updates at {datetime.now()}")
    check_for_updates()

def run_scheduler():
    print("Starting the scheduler...")
    job()  # Run the job immediately
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)

# Flask Routes
@app.route('/')
def index():
    items = get_stored_items()
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Chiikawa Market Tracker</title>
            <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;700&display=swap" rel="stylesheet">
            <style>
                body {
                    font-family: 'Nunito', sans-serif;
                    background-color: #FFF5E6;
                    color: #4A4A4A;
                    margin: 0;
                    padding: 20px;
                }
                .header {
                    text-align: center;
                    margin-bottom: 30px;
                }
                .header img {
                    max-width: 320px;
                    width: 100%;
                    height: auto;
                }
                h1 {
                    text-align: center;
                    color: #FF9999;
                    font-size: 2.5em;
                    margin: 20px 0;
                }
                .products-container {
                    display: flex;
                    flex-wrap: wrap;
                    justify-content: center;
                    gap: 20px;
                }
                .product {
                    background-color: #FFFFFF;
                    border-radius: 15px;
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    padding: 15px;
                    width: 200px;
                    text-align: center;
                    transition: transform 0.3s ease;
                }
                .product:hover {
                    transform: translateY(-5px);
                }
                .product img {
                    max-width: 100%;
                    height: auto;
                    border-radius: 10px;
                }
                .product a {
                    text-decoration: none;
                    color: inherit;
                }
                .product h3 {
                    font-size: 1em;
                    margin: 10px 0;
                    color: #4A4A4A;
                }
                .product p {
                    font-weight: bold;
                    color: #FF9999;
                }
                .chiikawa-footer {
                    text-align: center;
                    margin-top: 30px;
                    font-size: 0.9em;
                    color: #999;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <img src="https://chiikawamarket.jp/cdn/shop/files/welcome_320x.png?v=16266376846941523964" alt="Chiikawa Welcome">
            </div>
            <h1>🐹 Chiikawa Market Tracker 🐾</h1>
            <div class="products-container">
                {% for item in items %}
                <div class="product">
                    <a href="{{ item.product_url }}" target="_blank">
                        <img src="https:{{ item.photo_url }}" alt="{{ item.name }}">
                        <h3>{{ item.name }}</h3>
                        <p>{{ item.price }}</p>
                    </a>
                </div>
                {% endfor %}
            </div>
            <div class="chiikawa-footer">
                Made with ❤️ for Chiikawa fans
            </div>
        </body>
        </html>
    ''', items=items)

def run_flask():
    app.run(debug=True, use_reloader=False)

if __name__ == "__main__":
    initialize_database()

    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run the scheduler in the main thread
    run_scheduler()
