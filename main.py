import os
from pprint import pprint
import requests
from bs4 import BeautifulSoup, Tag
import time
import sqlite3
from datetime import datetime
from typing import TypedDict, List
import schedule
from pync import Notifier
from flask import Flask, render_template_string, request
import threading
import webbrowser
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Product(TypedDict):
    name: str
    photo_url: str
    price: str
    product_url: str
    is_sold_out: bool
    product_number: str

# Configuration
DATABASE_NAME = 'chiikawa_items.db'
CHIIKAWA_URL = "https://chiikawamarket.jp/collections/newitems"
CHECK_INTERVAL_MINUTES = 5
CLIENT_PORT = 3001

app = Flask(__name__)

# Database Operations
def initialize_database() -> None:
    with sqlite3.connect(DATABASE_NAME) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS items
                     (name TEXT, photo_url TEXT, price TEXT, product_url TEXT, date_added TEXT, is_latest INTEGER, is_sold_out INTEGER, product_number TEXT)''')

def store_items(items: List[Product]) -> None:
    with sqlite3.connect(DATABASE_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE items SET is_latest = 0")
        for item in items:
            c.execute("""
                INSERT INTO items (name, photo_url, price, product_url, date_added, is_latest, is_sold_out, product_number)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """, (item['name'], item['photo_url'], item['price'], item['product_url'], datetime.now().isoformat(), item['is_sold_out'], item['product_number']))

def get_stored_items() -> List[Product]:
    with sqlite3.connect(DATABASE_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT name, photo_url, price, product_url, is_sold_out, product_number FROM items WHERE is_latest = 1")
        return [{'name': row[0], 'photo_url': row[1], 'price': row[2], 'product_url': row[3], 'is_sold_out': bool(row[4]), 'product_number': row[5]} for row in c.fetchall()]

# Web Scraping
def fetch_website_content(url: str, page: int = 1) -> str:
    full_url = f"{url}?page={page}" if page > 1 else url
    response: requests.Response = requests.get(full_url)
    return response.text

def get_max_page_number(html_content: str) -> int:
    soup = BeautifulSoup(html_content, 'html.parser')
    pagination = soup.find('div', class_='pagination--root')
    if pagination:
        last_page = pagination.find_all('li', class_='pagination--number')[-1]
        return int(last_page.text)
    return 1  # If no pagination found, assume only one page

def parse_items(html_content: str) -> List[Product]:
    soup: BeautifulSoup = BeautifulSoup(html_content, 'html.parser')
    items: List[Tag] = soup.find_all('div', class_='product--root')

    products: List[Product] = []

    for item in items:
        anchor_tag = item.find('a', href=True)
        product_url = f"https://chiikawamarket.jp{anchor_tag['href']}" if anchor_tag else ''
        product_number = product_url.split('/')[-1] if product_url else ''

        img_tag = item.find('img', class_='lazyload')
        photo_url = img_tag['data-src'].replace('{width}', '1200') if img_tag and 'data-src' in img_tag.attrs else ''

        sold_out_label = item.find('div', class_='product--label', string='売り切れ')
        is_sold_out = bool(sold_out_label)

        product: Product = {
            'name': item.find('h2', class_='product_name').text.strip(),
            'photo_url': photo_url,
            'price': item.find('div', class_='product_price').text.strip(),
            'product_url': product_url,
            'is_sold_out': is_sold_out,
            'product_number': product_number
        }

        products.append(product)

    return products

# Notification
def send_notification(new_items: List[Product]) -> None:
    logger.info("New items found:")
    notification_text = "\n".join([f"{item['name']} - {item['price']}" for item in new_items])
    logger.info(notification_text)

    Notifier.notify(
        message=notification_text,
        title="New Chiikawa Items!",
        open=CHIIKAWA_URL,
        sound='Blow',
        contentImage='chiikawa.png'
    )
    
    webbrowser.open(f"http://127.0.0.1:{CLIENT_PORT}")

# Main Logic
def check_for_updates() -> None:
    html_content: str = fetch_website_content(CHIIKAWA_URL)
    max_page = get_max_page_number(html_content)

    logger.info(f"Found {max_page} pages of items")
    logger.info("Fetching page 1")
    current_items: List[Product] = parse_items(html_content)
    stored_items: List[Product] = get_stored_items()
    
    new_items: List[Product] = [item for item in current_items if item['product_number'] not in [stored_item['product_number'] for stored_item in stored_items]]

    if not new_items:
        logger.info(f"No new items found on the first page at {datetime.now()}")
        return

    all_new_items = new_items.copy()

    for page in range(2, max_page + 1):
        logger.info(f"Fetching page {page} of {max_page}")
        page_content = fetch_website_content(CHIIKAWA_URL, page)
        page_items = parse_items(page_content)

        all_new_items.extend(page_items)

    # This will now set all existing items as not latest, and new items as latest
    store_items(all_new_items)
    send_notification(all_new_items)
    logger.info(f"Found and stored {len(all_new_items)} new items")

def job():
    logger.info(f"Checking for updates at {datetime.now()}")
    check_for_updates()

def run_scheduler():
    logger.info("Starting the scheduler...")
    job()  # Run the job immediately
    schedule.every(CHECK_INTERVAL_MINUTES).minutes.do(job)

    while True:
        schedule.run_pending()
        time.sleep(1)

# Flask Routes
@app.route('/')
def index():
    filter_option = request.args.get('filter', 'all')
    items = get_stored_items()
    if filter_option == 'available':
        items = [item for item in items if not item['is_sold_out']]
    elif filter_option == 'sold_out':
        items = [item for item in items if item['is_sold_out']]
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
                    position: relative;
                    overflow: hidden;
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
                .sold-out {
                    position: absolute;
                    top: 10px;
                    right: -35px;
                    background-color: #FF0000;
                    color: white;
                    padding: 5px 40px;
                    transform: rotate(45deg);
                    font-size: 0.8em;
                    font-weight: bold;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                }
                .filter-container {
                    text-align: center;
                    margin-bottom: 20px;
                }
                .filter-container select {
                    padding: 5px 10px;
                    font-size: 1em;
                    border-radius: 5px;
                    border: 1px solid #FF9999;
                    background-color: #FFF;
                    color: #4A4A4A;
                }
                .chiikawa-footer {
                    text-align: center;
                    margin-top: 30px;
                    font-size: 0.9em;
                    color: #999;
                }
                .product_number {
                    font-size: 0.8em;
                    color: #999;
                    margin-top: 5px;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <img src="https://chiikawamarket.jp/cdn/shop/files/welcome_320x.png?v=16266376846941523964" alt="Chiikawa Welcome">
            </div>
            <h1>🐹 Chiikawa Market Tracker 🐾</h1>
            <div class="filter-container">
                <label for="filter">Filter: </label>
                <select id="filter" onchange="window.location.href='?filter=' + this.value">
                    <option value="all" {% if filter_option == 'all' %}selected{% endif %}>All</option>
                    <option value="available" {% if filter_option == 'available' %}selected{% endif %}>Available</option>
                    <option value="sold_out" {% if filter_option == 'sold_out' %}selected{% endif %}>Sold Out</option>
                </select>
            </div>
            <div class="products-container">
                {% for item in items %}
                <div class="product">
                    {% if item.is_sold_out %}
                    <div class="sold-out">売り切れ</div>
                    {% endif %}
                    <a href="{{ item.product_url }}" target="_blank">
                        <img src="https:{{ item.photo_url }}" alt="{{ item.name }}">
                        <h3>{{ item.name }}</h3>
                        <p>{{ item.price }}</p>
                        <div class="product_number">{{ item.product_number }}</div>
                    </a>
                </div>
                {% endfor %}
            </div>
            <div class="chiikawa-footer">
                Made with ❤️ for Chiikawa fans
            </div>
        </body>
        </html>
    ''', items=items, filter_option=filter_option)

def run_flask():
    app.run(debug=True, use_reloader=False, port=CLIENT_PORT)

if __name__ == "__main__":
    initialize_database()

    # Start the Flask app in a separate thread
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    # Run the scheduler in the main thread
    run_scheduler()