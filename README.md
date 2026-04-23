# Automated Audio-to-Notes Pipeline 🎙️📝

> ⚠️ **Note:** The core logic and Python source code are currently kept in a private, closed-source repository due to upcoming commercialization. This repository serves as an architectural overview and technical showcase of my AI-native engineering capabilities.

### 🛠️ Tech Stack & Infrastructure

**Frontend & UI**
<p align="left">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit" />
  <img src="https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white" alt="HTML5" />
  <img src="https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="CSS3" />
  <img src="https://img.shields.io/badge/Markdown-000000?style=for-the-badge&logo=markdown&logoColor=white" alt="Markdown" />
</p>


**Backend & Data Processing**
<p align="left">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />
  <img src="https://img.shields.io/badge/JSON-000000?style=for-the-badge&logo=json&logoColor=white" alt="JSON" />
  <img src="https://img.shields.io/badge/TheFuzz-FF9900?style=for-the-badge" alt="TheFuzz" />
</p>

**AI Models & Inference Engine**
<p align="left">
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch" />
  <img src="https://img.shields.io/badge/OpenAI_Whisper-412991?style=for-the-badge&logo=openai&logoColor=white" alt="Whisper STT" />
  <img src="https://img.shields.io/badge/Mistral_7B-F54E42?style=for-the-badge&logo=alibabacloud&logoColor=white" alt="Mistral AI" />
  <img src="https://img.shields.io/badge/LM_Studio-5A29E4?style=for-the-badge&logo=openai&logoColor=white" alt="LM Studio" />
  <img src="https://img.shields.io/badge/CUDA_/_MPS-76B900?style=for-the-badge&logo=nvidia&logoColor=white" alt="CUDA Acceleration" />
</p>

**DevOps & Security**
<p align="left">
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Nginx_Proxy-009639?style=for-the-badge&logo=nginx&logoColor=white" alt="Nginx" />
  <img src="https://img.shields.io/badge/Bcrypt_Hashing-4A154B?style=for-the-badge&logo=springsecurity&logoColor=white" alt="Bcrypt" />
  <img src="https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white" alt="FFmpeg" />
  <img src="https://img.shields.io/badge/DotEnv-ECD53F?style=for-the-badge&logo=dotenv&logoColor=black" alt="Dotenv" />
</p>


## 📌 Project Overview
The **Automated Audio-to-Notes Pipeline** (internally code-named *SafeMed AI*) is an advanced, locally-hosted AI application designed for professionals (doctors, lawyers, notaries). It automatically transcribes audio recordings and processes them through Large Language Models (LLMs) to generate structured, professional documentation—such as medical SOAP notes or legal protocols—while maintaining strict data privacy.

## 📸 Visual Showcase: UI & UX
### 1. Enterprise-Grade Authentication System
The application is gated by a robust, custom-built authentication layer designed to meet the strict security requirements of medical and legal environments. Because Streamlit inherently lacks built-in authentication, I engineered a secure session-state guard that completely halts application rendering (`st.stop()`) until valid credentials are provided.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/auth_login_screen.png" alt="Ekran logowania" width="1000" />

**Under the Hood (Security Architecture):**
*   **Advanced Cryptography:** Passwords are never stored in plain text. The system utilizes `bcrypt` with a high work factor (14 rounds), combined with a server-side Environment Pepper (`.env`), making rainbow-table and dictionary attacks computationally unfeasible.
*   **Anti-Brute-Force Mechanism:** 
    *   A custom SQLite (WAL mode) backend tracks failed login attempts.
    *   Triggers an automatic **15-minute account lockout** after 5 consecutive failed attempts.
    *   Implements an intentional artificial delay (`time.sleep(2)`) on failed logins to heavily throttle automated attack scripts.
*   **Audit Logging:** Every login attempt (Success/Failure) is recorded by a custom `RotatingFileHandler` logger, capturing the user ID, timestamp, and action status to maintain a compliant security audit trail.
*   **Password Policy Enforcement:** Built-in regex validators enforce strong password creation (minimum 12 characters, requiring uppercase, lowercase, and numeric digits) during account updates.


### 2. Main Interface: Context-Aware AI
A distraction-free environment for audio processing and document generation.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/dashboard_main_ui.png" alt="Główny interfejs" width="1000" />

**Key Features:**
*   **Role Selection:** Users choose from specialized profiles: Medical (SOAP), Notary (Protocol), or Legal (Analysis). Each profile injects a different system prompt into the LLM.
*   **Asynchronous Upload & Processing:** Uploading audio triggers a real-time progress indicator (`st.status`). The UI remains responsive while the backend processes large files.

### 3. Personal Visit History & Session Recovery
Automatic, user-isolated tracking of daily activity.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/session_history_sidebar.png" alt="Historia wizyt w panelu bocznym" width="1000" />

**Key Features:**
*   **Private Daily Log:** The sidebar queries the SQLite database to display only the current user's generated documents for that specific day.
*   **Instant Recovery:** Clicking "Przywróć tę wizytę" (Restore) instantly reloads a previous session's output from the database into the main view, preventing data loss.
*   **Visual Indicators:** Icons (🩺, 📜, ⚖️) quickly identify which AI profile was used for each historical entry.


### 4. Account Security & Role Management
The sidebar includes a dedicated expander for user account security.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/user_account_management.png" alt="Zarządzanie kontem i profil" width="1000" />

**Key Features:**
*   **Self-Service Password Updates:** Users can securely change their passwords directly from the sidebar. The form enforces strict complexity rules (min. 12 chars, uppercase, lowercase, numbers).
*   **Cryptographic Verification:** Requires validation of the old password against the database hash before generating a new `bcrypt` salt for the update.
*   **Role-Based Visibility:** Standard users see only the password change form. If logged in as the 'System Administrator', a hidden panel dynamically renders, allowing the manager to view and delete staff accounts from the SQLite database.


## ⚙️ Core AI Pipeline: Audio to Structured Data
The primary function of the application is converting raw audio into structured, domain-specific documentation using a tightly controlled pipeline.

### 1. Context-Aware Prompt Injection
Before uploading audio, the user selects a specialized AI agent (Medical, Notary, or Legal Analyst).

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/agent_profile_selection.png" alt="Wybór profilu asystenta" width="1000" />

**How it works:**
*   **Dynamic Context:** Each mode maps to a distinct, hardcoded system prompt instructing the LLM on output structure (e.g., SOAP format for medical, formal declarations for legal).
*   **Strict Filtration Rules:** The prompts contain explicit instructions (e.g., "ZIGNORUJ CAŁKOWICIE: small talk") to force the LLM to strip out conversational noise and focus solely on diagnostic or legal facts.

### 2. Asynchronous STT Processing (Whisper)
The user uploads a media file (MP3/WAV/MP4), which is immediately dispatched to a local Speech-to-Text server.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/audio_upload_processing.png" alt="Wgrywanie pliku audio" width="1000" />

**How it works:**
*   **Non-Blocking Polling:** Instead of freezing the Streamlit app during long transcriptions, the audio is sent to an asynchronous FastAPI endpoint (`/async`). 
*   **Fragment-Based Updates:** A Streamlit fragment (`@st.fragment(run_every=2)`) constantly polls the STT server for the task status. This allows the UI to display live progress indicators (`st.status`) while waiting for the final text.

### 3. LLM Inference & Output Validation
Once the raw transcript is ready, it is passed to the local LLM (e.g., Qwen) for structuring. 

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/generated_clinical_note.png" alt="Gotowa notatka" width="1000" />

**How it works:**
*   **VRAM Protection:** Before hitting the LLM, the system executes `gc.collect()` and `torch.cuda.empty_cache()` within a global `threading.Lock()`. This prevents GPU Out-Of-Memory (OOM) crashes in environments with concurrent requests.
*   **Fuzzy Medical Validation:** In Medical mode, the LLM outputs a raw list of medications. The system parses this list and uses fuzzy string matching (`thefuzz`) against a local dictionary (`leki_pro.csv`). Verified drugs are marked green (✅), while hallucinated or misspelled drugs are flagged with a critical warning (⚠️).
*   **Actionable Export:** The generated text is locked behind a mandatory validation checkbox. Once checked, the user can copy the text or export it as a valid FHIR JSON `DocumentReference` resource.


### 4. Output Validation & Medical Safeguards
Before the final document is presented to the user, the system performs a crucial safety check to prevent AI hallucinations, especially regarding medical treatments.

**How it works:**
*   **Dictionary Cross-Referencing:** The LLM is instructed to isolate generated medication names. A background Python script (`wyciagacznazwlekow.py`) uses the `thefuzz` library to cross-reference these generated names against an official, comprehensive medical registry (`leki_pro.csv`).
*   **Visual Confidence Scoring:** 
    *   Verified matches (score > 90%) are marked in green (✅) directly in the generated text.
    *   Unrecognized or misspelled drugs are flagged with a critical warning indicator (⚠️), reducing cognitive load and allowing physicians to quickly review the note with confidence.
*   **Anti-Mindless Copying (Liability Lock):** To enforce legal and medical responsibility, the UI intentionally disables all export actions by default. Users cannot simply copy the text or download the FHIR JSON until they explicitly check a mandatory declaration ("I declare that I have verified the correctness of the medical data..."). This creates an intentional friction point that forces active human-in-the-loop review.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/secure_data_export.png" alt="Bezpieczny eksport danych" width="1000" />

### 5. System Observability & RODO/GDPR Auditing
To meet the stringent compliance and operational requirements of modern healthcare and legal institutions, the application features a dedicated, real-time Analytics Dashboard.

<img src="https://raw.githubusercontent.com/JedrasiakJan/Automated-Audio-to-Notes-Pipeline/main/assets/analytics_dashboard_observability.png" alt="Panel analityczny" width="1000" />

**How it works:**
*   **Live Performance Metrics:** The system continuously parses the localized `app.log` file (managed via `RotatingFileHandler`) to calculate and visualize the average inference times for both the Whisper (STT) and LLM models.
*   **Visual Analytics:** Performance trends over time and workload distribution (boxplots) are dynamically rendered, allowing administrators to monitor hardware bottlenecks (like GPU/VRAM strain) and optimize deployment scaling.
*   **Compliance Auditing:** A dedicated section provides a searchable interface for specific user sessions. This serves as a vital tool for RODO/GDPR compliance, maintaining a cryptographically secure, immutable audit trail of who generated what document and when.

## 🐳 Deployment & Containerization Architecture
To ensure the application is portable, scalable, and isolated from the host operating system, the entire pipeline is containerized using Docker and orchestrated with Docker Compose.

**Deployment Strategy:**
*   **Multi-Container Setup:** 
    *   `medical-ai`: The core Streamlit/Python application built from a custom lightweight `python:3.10-slim` image, pre-configured with system-level dependencies like FFmpeg for audio processing.
    *   `nginx`: A dedicated reverse proxy container acting as a "gatekeeper" in front of the application.
*   **Network Isolation:** The Streamlit app runs internally on port `8501`, but this port is **not** exposed to the outside network. All external traffic must pass through the Nginx container on standard HTTP port `80`.
*   **Double Authentication Layer:** Before a user even reaches the Streamlit application's internal login screen, Nginx enforces an HTTP Basic Authentication (`.htpasswd`) wall, providing an additional layer of security against unauthorized access or scanning bots.
*   **Resource Throttling:** Hardware resource limits are explicitly defined in `docker-compose.yml` (e.g., `memory: 8gb`), preventing the AI assistant container from monopolizing host system memory.



## 🏁 Summary
The **Automated Audio-to-Notes Pipeline** is a comprehensive demonstration of full-stack AI engineering. It bridges the gap between raw machine learning models and enterprise-ready software by implementing robust security, asynchronous data processing, strict output validation, and a production-grade Dockerized deployment strategy.
