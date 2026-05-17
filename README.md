# DevSync AI: Autonomous Curation Engine

<div align="center">
  <img src="https://img.shields.io/badge/Status-Completed-success" alt="Status Completed">
  <img src="https://img.shields.io/badge/Python-3.10+-blue" alt="Python Version">
  <img src="https://img.shields.io/badge/Framework-Streamlit-FF4B4B" alt="Framework Streamlit">
  <img src="https://img.shields.io/badge/Database-SQLAlchemy-red" alt="Database">
  <img src="https://img.shields.io/badge/AI-OpenAI%20%7C%20Anthropic-orange" alt="AI Models">
</div>

<br>

**DevSync AI** is a production-grade, cloud-native data pipeline designed to mitigate information overload for multi-domain technology professionals. It autonomously scrapes, semantically evaluates, and distributes personalized industry intelligence utilizing Large Language Models (LLMs).

---

## 🚀 Key Features

* **Autonomous Data Ingestion:** Background cron jobs seamlessly extract raw text and metadata from technical blogs and the YouTube Data API v3.
* **Semantic Reasoning (CuratorAgent):** Utilizes OpenAI/Anthropic APIs to evaluate raw content against specific user domain tags (e.g., MLOps, Docker), assigning a quantitative score (1-10) and an Explainable AI (XAI) summary.
* **Role-Based Access Control (RBAC):** Strict separation of privileges. Features a public guest feed, an authenticated subscriber dashboard, and an exclusive Control Center for administrators.
* **Stateless Authentication:** Implements highly secure, passwordless entry using cryptographically generated single-use **Magic Links**.
* **Automated Distribution:** An asynchronous daemon compiles top-ranked daily intelligence and dispatches formatted HTML email digests via SMTP.

---

## 🏗️ System Architecture

DevSync AI operates on a strictly decoupled multi-tier architecture to ensure UI responsiveness while handling heavy LLM reasoning tasks asynchronously.

### The Autonomous Pipeline
1. **Acquisition:** Raw HTML/JSON is fetched and cleaned.
2. **Evaluation:** The `CuratorAgent` processes chunks and maps them to User Interest Tags.
3. **Storage:** Structured relational mapping of `Users`, `Articles`, and personalized `AI_Rankings`.
4. **Presentation:** Reactive DOM rendering via Streamlit.

*(Note: The full system design includes Level-1 Data Flow Diagrams (DFDs) and comprehensive Relational Database Schemas mapping the User, Content, and Intelligence entities.)*

---

## 🛠️ Technology Stack

| Tier | Technologies Used |
| :--- | :--- |
| **Presentation (Frontend)** | Python, Streamlit |
| **Logic (Backend)** | Python, Background Schedulers (Cron) |
| **Database (ORM)** | PostgreSQL / SQLite, SQLAlchemy |
| **External APIs** | OpenAI API, Anthropic API, YouTube Data API v3 |
| **Distribution** | SMTP Gateway |

---

## 🔒 Security & Performance Highlights

* **Zero-Password Policy:** Eliminates hash-cracking vulnerabilities via Magic Link tokens.
* **Environment Isolation:** All sensitive credentials and external API keys are strictly managed via `.env`.
* **Sub-3 Second UI Rendering:** Achieved by executing all LLM reasoning entirely out of the user request cycle (asynchronous pre-calculation).
* **API Rate Limiting Protection:** Implements algorithmic delays and exponential backoff to handle HTTP 429 errors from external LLM providers gracefully.

---

## 📬 Contact & Availability

This repository serves as a public showcase of the DevSync AI architecture and capabilities. The core source code and proprietary pipeline logic remain private.

If you are interested in acquiring this project, collaborating, or discussing the architecture further, please contact:

**📧 Email:** [majidhussain3897@gmail.com](mailto:majidhussain3897@gmail.com)

---
*Designed and Developed by Majid Hussain.*