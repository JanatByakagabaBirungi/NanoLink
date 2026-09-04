# NanoLink: A RESTful URL Shortener API

NanoLink is a high-performance URL shortening service built with Python and Flask. It takes long URLs, generates compact hashes (or custom aliases), stores them in a local SQLite database, and handles fast HTTP redirects. 

Designed with a focus on developer experience, it includes click analytics, QR code generation, and is fully containerized for instant deployment.

## ✨ Features
*   **Fast Redirection:** Low-latency redirects from short hashes to original URLs.
*   **Custom Aliases:** Users can define their own branded short links.
*   **Analytics Tracking:** Records total click counts and timestamps for every shortened URL.
*   **QR Code Integration:** Automatically generates QR codes for easy mobile sharing.
*   **Input Validation:** Built-in URL validation and error handling.
*   **Containerized:** Fully Dockerized for seamless local setup and deployment.

## 🛠 Tech Stack
*   **Backend:** Python, Flask
*   **Database:** SQLite (using SQLAlchemy ORM)
*   **Containerization:** Docker, Docker Compose
*   **Additional Libraries:** `qrcode` (for image generation), `validators` (for URL parsing)

## 🚀 Quick Start (Docker)

The easiest way to run the application is via Docker.

1. Clone the repository:
   ```bash
   git clone [https://github.com/JanatByakagabaBirungi/NanoLink.git](https://github.com/JanatByakagabaBirungi/NanoLink.git)
   cd NanoLink
