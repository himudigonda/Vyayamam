# Vyayamam 🏋️ - Your Hyper-Personalized AI Workout Coach

**Version:** 3.5 (AI-Integrated, Local-First)
**Status:** System Complete

Vyayamam is a fully local, private, and intelligent fitness partner that runs on your machine and communicates with you via WhatsApp. It's designed to be a frictionless workout logger and a data-driven coach, helping you track progress, stay consistent, and get deep, AI-powered insights into your training.

The entire system is built on free, open-source, and locally-hosted technologies, ensuring your data remains 100% private and you have zero operational costs.

---

## ✨ Core Features

### 💬 Conversational Interface (WhatsApp)

*   **Flexible Workout Logging:** Log your sets with a simple message. Thanks to fuzzy matching, the system understands typos and variations.
    *   `smith incline 120 8`
    *   `db shoulderpress 50 10 rpe 8`
    *   `leg press 300 10 notes form felt great`
*   **Proactive Coaching (`next`):** After an exercise, type `next` and the bot will tell you what's next in your plan, complete with historical performance, your PR, and a suggested target weight for progressive overload.
*   **Smart Session Management (`/start`, `/end`):** Use `/start` and `/end` to bracket your workout. When you end a session, you receive an automated grade (A+ to F) and a celebratory, AI-generated summary of your performance.
*   **Daily Readiness Logging (`/sleep`, `/stress`, `/soreness`):** Quickly log key recovery metrics that are then visualized on the dashboard.
*   **On-Demand AI Analyst (`/ask`):** Ask complex questions in plain English (`/ask how is my squat progressing?`). The bot uses a local LLM to analyze your recent data and provide detailed, quantitative insights.
*   **Discoverability (`/list`, `/help`):**
    *   `/list`: Shows the planned exercises for today.
    *   `/list all`: Shows every single loggable exercise in your entire program.
    *   `/help`: Displays a comprehensive menu of all available commands.

### 📊 Rich Analytics Dashboard (Web Interface)

A comprehensive web dashboard (built with Streamlit) to visualize your long-term progress:

*   **Strength Progression (e1RM):** Tracks your calculated "Estimated 1-Rep Max" for key compound lifts, the gold standard for measuring pure strength gain.
*   **Volume Trends:** Interactive charts showing total volume (Weight x Reps x Sets) for selected exercises over time.
*   **Personal Record (PR) Tracker:** An auto-updating table of your best lift (by weight) for every exercise you've ever performed.
*   **Muscle Group Balance:** A weekly stacked bar chart showing volume distribution across muscle groups (Chest, Back, Legs, etc.) to ensure balanced training.
*   **Readiness vs. Performance:** A dual-axis chart correlating your logged sleep and stress with your daily workout volume, revealing how recovery impacts performance.
*   **Consistency Heatmap:** A GitHub-style calendar that provides a powerful at-a-glance visualization of your workout frequency and dedication.
*   **Dashboard AI Insight:** A button to trigger the same powerful AI analysis engine directly from the web interface.

### 🔒 System & Architecture

*   **100% Private & Local-First:** Your workout data never leaves your control. It's stored in a local MongoDB database, and all AI analysis happens on your machine with Ollama.
*   **Secure by Design:** The webhook is protected by Twilio request validation, ensuring that only legitimate requests from Twilio can access your application.
*   **Data Safety:** A simple command-line script (`scripts/backup.py`) allows for one-command, timestamped backups of your entire database.

---

## 🏗️ System Architecture

The system uses a clever hybrid approach to connect the public WhatsApp network to your private, local machine.

```
                  INTERNET                                         YOUR LOCAL MACBOOK
+------------------------------------------+    +-------------------------------------------------------------+
|                                          |    |                                                             |
|  +----------+     +---------+     +----------+ | +------------------+     +-----------------+     +---------+  |
|  | WhatsApp | --> | Twilio  | --> |  Ngrok   |-->|  FastAPI Server  | --> |   MongoDB       | <-- | Ollama  |  |
|  +----------+     +---------+     +----------+ | | (localhost:8000) | <-- | (localhost:27017) | --> | (LLM)   |  |
|                                          |    | +------------------+     +-----------------+     +---------+  |
|                                          |    |         ^                                                     |
|                                          |    |         |                                                     |
|                                          |    |         v                                                     |
|                                          |    |  +--------------------+                                       |
|                                          |    |  | Streamlit Dashboard|                                       |
|                                          |    |  | (localhost:8501)   |                                       |
|                                          |    |  +--------------------+                                       |
+------------------------------------------+    +-------------------------------------------------------------+
```

---

## 🛠️ Technology Stack

*   **Backend:** 🐍 Python 3.11+ with 🚀 FastAPI & Uvicorn
*   **Database:** 🍃 MongoDB (running locally via Docker)
*   **AI Engine:** 🧠 Ollama with a local model (e.g., `gemma3` or `llama3`)
*   **Dashboard:** 📊 Streamlit with Pandas & Plotly
*   **Messaging:** 💬 Twilio API for WhatsApp
*   **Tunneling:** 🚇 Ngrok
*   **Fuzzy Matching:** `thefuzz` for flexible text parsing
*   **Environment:** `uv` for package management
*   **Security:** `PyNaCl` for request validation

---

## 🚀 Setup and Installation

Follow these steps to get your Vyayamam coach running.

### 1. Prerequisites

Make sure you have the following installed on your machine:
*   [Python 3.11+](https://www.python.org/downloads/)
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/)
*   [Ollama](https://ollama.com/)
*   [Ngrok](https://ngrok.com/download)
*   An active [Twilio](https://www.twilio.com/try-twilio) account with a WhatsApp Sandbox setup.

### 2. Clone and Configure

```bash
git clone https://github.com/himudigonda/vyayamam.git
cd vyayamam

# Run the setup script to create directories and the .env file
chmod +x setup.sh
./setup.sh

# Edit the .env file with your credentials
nano .env 
```
Fill in your `MONGO_URI`, `DB_NAME`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, and `ADMIN_PHONE_NUMBER`.

### 3. Install Dependencies

```bash
# Activate the virtual environment
source .venv/bin/activate

# Install all required Python packages
uv pip install -r requirements.txt
```

### 4. Set Up Local Services

1.  **Start MongoDB with Docker:**
    ```bash
    # This name is important for the backup script
    docker run --name vyayamam-mongo -d -p 27017:27017 mongo
    ```
2.  **Start Ollama & Pull a Model:** Launch the Ollama application. Then, in your terminal:
    ```bash
    ollama pull gemma3:latest
    ```
3.  **Seed the Database with Your Workout Plan:** This script populates the database with the initial exercise definitions.
    ```bash
    uv run python scripts/seed_db.py
    ```
4.  **(Optional) Populate with Fake Data:** To test the dashboard with a month's worth of data, run the populate script. **Warning: This erases all existing logs.**
    ```bash
    uv run python scripts/populate.py
    ```

### 5. Running the System

To run the full system, you will need **3 terminal windows/tabs** running concurrently.

1.  **Terminal 1: Start the FastAPI Backend**
    ```bash
    # (make sure .venv is active)
    uvicorn app.main:app --reload
    ```
2.  **Terminal 2: Start the Analytics Dashboard**
    ```bash
    # (make sure .venv is active)
    streamlit run dashboard/dashboard.py
    ```
3.  **Terminal 3: Start the Ngrok Tunnel**
    ```bash
    # Expose your local port 8000 to the internet
    ngrok http 8000
    ```
    Copy the `https://....ngrok-free.app` URL from the Ngrok output.

### 6. Final Configuration: Link Ngrok to Twilio

*   Go to your [Twilio WhatsApp Sandbox settings](https://console.twilio.com/us1/develop/messaging/try-it-out/whatsapp-senders).
*   In the **"WHEN A MESSAGE COMES IN"** field, paste your Ngrok URL and append `/api/whatsapp`.
    *   **Example:** `https://your-random-id.ngrok-free.app/api/whatsapp`
*   Set the method to `HTTP POST` and click **Save**.

Your system is now live! Send `/help` to your bot on WhatsApp to see all commands.

---

## 🛡️ Data Backup

Your training data is valuable. To create a safe, compressed, timestamped backup of the database, simply run:
```bash
# (make sure .venv is active and the vyayamam-mongo container is running)
uv run python scripts/backup.py
```
Your backup file will be saved in the `backups/` directory.

---
## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
```

This new `README.md` is a complete and accurate representation of the fantastic system you have built. It serves as a perfect final document for the project.
