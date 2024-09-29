# Chiikawa Market Tracker

A Python application that monitors the Chiikawa Market website for new items, sends notifications, and provides a web interface to display tracked items.

## Features

- Automatically checks for new items on Chiikawa Market
- Sends desktop notifications for new items
- Web interface to view all tracked items

## Quick Start

You may want to use a virtual environment to avoid conflicts with other Python projects.

1. Install required packages:
    ```bash
    pip install -r requirements.txt
    ```

2. Run the application:
    ```bash
    python main.py
    ```

3. Open the web interface in your browser:
    ```
    http://localhost:5000
    ```

The tracker will check for new items every 5 minutes and send notifications when new products are found.

## Configuration

Edit these variables in `main.py` to customize:

- `DATABASE_NAME`: SQLite database file name
- `CHIIKAWA_URL`: Chiikawa Market URL to monitor
- `CHECK_INTERVAL_MINUTES`: Time between checks

## Note

This project is for educational purposes only. Please respect the terms of service of the websites you interact with.
