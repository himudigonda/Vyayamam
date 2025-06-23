# Vyayamam 🏋️ - Your Hyper-Personalized AI Workout Coach

Vyayamam is a fully local, private, and intelligent fitness partner that runs on your machine and communicates with you via WhatsApp. It's designed to be an effortless workout logger and a data-driven coach, helping you track progress, stay consistent, and get AI-powered insights into your training.

The entire system is built on free, open-source, and locally-hosted technologies, ensuring your data remains 100% private and you have zero operational costs.

## ✨ Core Features

*   **📱 Real-time WhatsApp Interface:** Log your sets with a simple message (`smith press 120 8`). No need to open another app.
*   **🤖 Proactive Coaching:** After an exercise, ask `next` and the bot will tell you what's next in your plan, complete with historical performance data and a suggested target weight.
*   **🧠 Conversational AI Analysis:** Ask questions in plain English (`/ask how is my chest progressing?`). The bot uses a local LLM (via Ollama) to analyze your recent data and provide detailed, qualitative insights.
*   **📊 Rich Analytics Dashboard:** A comprehensive web dashboard (built with Streamlit) to visualize your long-term progress, including:
    *   📈 Volume trends for key exercises.
    *   🏆 A Personal Record (PR) tracker.
    *   🗓️ A GitHub-style consistency heatmap.
*   **🔒 100% Private & Local-First:** Your workout data never leaves your control. It's stored in a local MongoDB database, and the AI analysis happens on your machine with Ollama.

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

## 🛠️ Technology Stack

*   **Backend:** 🐍 Python 3.11+ with 🚀 FastAPI & Uvicorn
*   **Database:** 🍃 MongoDB (running locally via Docker)
*   **AI Engine:** 🧠 Ollama with a local model (e.g., `gemma3` or `llama3`)
*   **Dashboard:** 📊 Streamlit with Pandas & Plotly
*   **Messaging:** 💬 Twilio API for WhatsApp
*   **Tunneling:** 🚇 Ngrok
*   **Environment:** `uv` for package management

## 🚀 Setup and Installation

Follow these steps to get your Vyayamam coach running.

### 1. Prerequisites

Make sure you have the following installed on your macOS machine:
*   [Python 3.11+](https://www.python.org/downloads/)
*   [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for running MongoDB)
*   [Ollama](https://ollama.com/)
*   [Ngrok](https://ngrok.com/download)
*   An active [Twilio](https://www.twilio.com/try-twilio) account with a WhatsApp Sandbox setup.

### 2. Clone the Repository

```bash
git clone https://github.com/himudigonda/vyayamam.git
cd vyayamam
```

### 3. Project Configuration

The project uses an `.env` file for all your secret keys and configurations.

1.  **Run the setup script:** This will create the necessary directories and an `.env` file from a template.
    ```bash
    chmod +x setup.sh
    ./setup.sh
    ```
2.  **Edit the `.env` file:** Open the newly created `.env` file and fill in your actual credentials.
    ```env
    # --- Vyayamam Environment Variables ---
    MONGO_URI="mongodb://localhost:27017/"
    DB_NAME="vyayamam_db"

    # --- Twilio Credentials ---
    TWILIO_ACCOUNT_SID="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    TWILIO_AUTH_TOKEN="your_twilio_auth_token"
    TWILIO_PHONE_NUMBER="whatsapp:+14155238886" # Your Twilio Sandbox Number
    ADMIN_PHONE_NUMBER="whatsapp:+12345678901" # Your Personal WhatsApp Number
    ```

### 4. Install Dependencies

The `setup.sh` script already created a virtual environment using `uv`.

1.  **Activate the virtual environment:**
    ```bash
    source .venv/bin/activate
    ```
2.  **Install all required Python packages:**
    ```bash
    uv pip install -r requirements.txt
    ```

### 5. Set Up Local Services

1.  **Start MongoDB with Docker:**
    ```bash
    docker run --name vyayamam-mongo -d -p 27017:27017 mongo
    ```
2.  **Start Ollama:** Launch the Ollama application on your Mac. Then, pull a model if you haven't already.
    ```bash
    ollama pull gemma3:latest
    ```
3.  **Seed the Database:** Run the script to populate your database with the workout plan.
    ```bash
    uv run python scripts/seed_db.py
    ```

## ⚡ Running the System

To run the full system, you will need **4 terminal windows/tabs** running concurrently.

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

4.  **Final Configuration: Link Ngrok to Twilio**
    *   Go to your [Twilio WhatsApp Sandbox settings](https://console.twilio.com/us1/develop/messaging/try-it-out/whatsapp-senders).
    *   In the **"WHEN A MESSAGE COMES IN"** field, paste your Ngrok URL and append `/api/whatsapp`.
    *   **Example:** `https://your-random-id.ngrok-free.app/api/whatsapp`
    *   Set the method to `HTTP POST` and click **Save**.

Your system is now live!

## 💬 How to Use Your Coach

Interact with your coach directly from WhatsApp.

### Logging a Set

Use the format: `{exercise} {weight} {reps}`. You can also add optional parameters.

*   `Dumbbell Rows 50 12`
*   `smith incline 120 8 rpe 7`
*   `leg press 300 10 notes form felt great`

### Getting Guidance

*   **`next`**: After finishing all sets for an exercise, type `next` to get a detailed breakdown of your next lift.
*   **`/ask [your question]`**: Ask the AI for analysis or information.
    *   `/ask how is my squat progressing?`
    *   `/ask analyze my last push day`
    *   `/ask what should I focus on if I feel my back is weak?`

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
