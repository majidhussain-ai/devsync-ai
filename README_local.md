# 🚀 AI News Aggregator

An autonomous, AI-powered research assistant designed to solve information overload. This system scrapes the web for the latest tech news, utilizes Large Language Models (LLMs) to curate and rank articles based on individual user preferences, and delivers highly personalized daily email digests.

## ✨ Key Features

* **Autonomous Ingestion:** Automated scrapers that continuously monitor YouTube channels, OpenAI, Anthropic blogs, and other tech sources.
* **Agentic AI Workflow:** Custom Python agents (`CuratorAgent`, `EmailAgent`) powered by the Google Gemini API for intelligent reading, ranking, and summarization.
* **Hyper-Personalization:** Delivers high-signal, low-noise content tailored to the specific professional interests of each user (e.g., MLOps, Data Engineering).
* **Robust Infrastructure:** Containerized database architecture ensuring a clean, reproducible, and production-ready environment.
* **Live Control Center:** A dynamic Streamlit dashboard for real-time monitoring, user management (CRUD), and data visualization using Altair.

## 🛠️ Tech Stack

* **Frontend & UI:** Streamlit, Altair, Pandas
* **AI & Reasoning:** Google Gemini API
* **Backend & ORM:** Python 3.13, SQLAlchemy
* **Database & Infrastructure:** PostgreSQL, Docker, Docker Compose
* **Package Management:** `uv`

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed on your system:
* Python 3.13+
* Docker and Docker Compose
* A valid Google Gemini API Key

## 🚀 Local Setup & Installation

Follow these precise steps to get the project running locally on your machine.

**1. Clone the Repository**
Navigate to your desired directory and clone the project:
> `git clone <your-repository-url>`
> `cd ai-news-aggregator`

**2. Environment Variables**
Create a `.env` file in the root directory and add your API credentials:
> `GEMINI_API_KEY=your_google_gemini_api_key_here`

**3. Start the Dockerized Database**
Initialize the PostgreSQL database in the background using Docker Compose:
> `cd docker`
> `docker-compose up -d`
> `cd ..`

**4. Activate the Virtual Environment & Install Dependencies**
This project uses `uv` for fast dependency management. Activate the existing environment:
> `source .venv/bin/activate`

*(Note: If dependencies are not installed, run `uv pip install -r requirements.txt`)*

**5. Launch the Application**
Start the Streamlit admin dashboard. Setting the `PYTHONPATH` ensures all local modules load correctly:
> `PYTHONPATH=. streamlit run app/dashboard.py`

---

## 🏗️ System Architecture

1. **Ingestion Layer:** Python scrapers gather raw data from predefined tech sources.
2. **Persistence Layer:** Raw articles and user profiles are stored safely in a Dockerized PostgreSQL database.
3. **Reasoning Layer:** The `CuratorAgent` fetches raw data and user profiles, utilizing the Gemini API to rank articles 1-10 based on relevance.
4. **Delivery Layer:** The `EmailAgent` crafts customized introductions and dispatches the final personalized digest to the user's inbox.

---
*Built for scale, resilience, and maximum signal-to-noise ratio.*