# 🩺 MedAssist — AI-Powered Medical Assistant

MedAssist is an AI-powered medical assistance platform designed to provide **symptom-based disease prediction, medical information retrieval, severity assessment, and AI-generated health guidance**.

The system combines a **Machine Learning classifier, Retrieval-Augmented Generation (RAG), ChromaDB, and MedGemma through Ollama** to provide contextual responses based on a user's symptoms.

> ⚠️ **Medical Disclaimer:** MedAssist is an experimental/educational AI system and is **not a replacement for a qualified medical professional**. Predictions and responses should not be used for diagnosis, treatment, or emergency medical decisions.

---

## ✨ Features

* 🧠 **Symptom-based disease prediction**

  * Random Forest classification model
  * Generates likely disease candidates from reported symptoms

* 📚 **Retrieval-Augmented Generation**

  * Retrieves relevant medical information using ChromaDB
  * Provides contextual information to the language model

* 🤖 **MedGemma integration**

  * Uses Google's MedGemma model through Ollama
  * Generates contextual medical responses locally

* 🚨 **Triage & severity assessment**

  * Estimates the urgency of reported symptoms
  * Helps distinguish between routine and potentially urgent situations

* 🔒 **Local AI inference**

  * LLM inference can run locally through Ollama
  * No external LLM API is required for the core inference pipeline

* ⚡ **FastAPI backend**

  * REST API for prediction and AI-assisted responses

* 💻 **React frontend**

  * Modern web interface built with React, TypeScript, and Vite

* 🗄️ **ChromaDB**

  * Vector database for medical knowledge retrieval

---

# 🏗️ Architecture

```text
                         ┌──────────────────────┐
                         │       User           │
                         │  Symptoms / Query    │
                         └──────────┬───────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │   React Frontend     │
                         │   TypeScript + Vite  │
                         └──────────┬───────────┘
                                    │
                              HTTP / REST
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │    FastAPI Backend   │
                         └──────────┬───────────┘
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                  ▼                 ▼                 ▼
          ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
          │ Random       │  │  ChromaDB    │  │    Triage    │
          │ Forest       │  │  Vector DB   │  │  / Severity  │
          │ Classifier   │  │              │  │              │
          └──────┬───────┘  └──────┬───────┘  └──────────────┘
                 │                 │
                 └────────┬────────┘
                          │
                          ▼
                  ┌─────────────────┐
                  │    MedGemma     │
                  │     4B          │
                  │     Ollama      │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ AI-Assisted     │
                  │ Medical Response│
                  └─────────────────┘
```

---

# 🛠️ Tech Stack

### Frontend

* React
* TypeScript
* Vite
* CSS

### Backend

* Python
* FastAPI
* Uvicorn

### Machine Learning

* Scikit-learn
* Random Forest

### RAG / Knowledge Retrieval

* ChromaDB
* Vector embeddings
* Retrieval-Augmented Generation

### LLM

* MedGemma 4B
* Ollama

---

# 📋 Requirements

Before running MedAssist locally, make sure you have:

* Python **3.13**
* Node.js **20+**
* npm
* Ollama
* Git

For GPU inference, a CUDA-compatible NVIDIA GPU is recommended.

---

# 🚀 Installation

## 1. Clone the repository

```bash
git clone https://github.com/safal999sapkota-collab/ARTEMIS-11.git
cd ARTEMIS-11
```

---

## 2. Create a Python virtual environment

### Linux / macOS

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

### Fish shell

```fish
python3.13 -m venv .venv
source .venv/bin/activate.fish
```

Verify:

```bash
python --version
```

Expected:

```text
Python 3.13.x
```

> **Note:** On Arch Linux, avoid installing project dependencies into the system Python. Use a virtual environment.

---

# 🤖 3. Install Ollama

Install Ollama for your operating system and make sure the Ollama server is running.

Start the server:

```bash
ollama serve
```

In another terminal, download MedGemma:

```bash
ollama pull medgemma:4b
```

Verify:

```bash
ollama list
```

You should see:

```text
medgemma:4b
```

---

# ⚙️ 4. Start the Backend

From the project root:

```bash
python run.py
```

The launcher handles the backend setup and starts the FastAPI application.

The backend should be available at:

```text
http://localhost:8000
```

FastAPI documentation:

```text
http://localhost:8000/docs
```

---

# 💻 5. Start the Frontend

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite will provide a local development URL, typically:

```text
http://localhost:5173
```

Open it in your browser.

---

# 🔐 Environment Variables

The backend environment configuration is stored in:

```text
backend/.env
```

A template is provided as:

```text
backend/.env.example
```

Create the environment file if necessary:

```bash
cp backend/.env.example backend/.env
```

Configure the values according to your local environment.

**Never commit secrets or private credentials to GitHub.**

---

# 📁 Project Structure

```text
ARTEMIS-11/
│
├── backend/
│   ├── ...
│   ├── .env.example
│   └── ...
│
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── ...
│
├── data/
│   └── ...
│
├── models/
│   └── ...
│
├── run.py
├── README.md
└── ...
```

> The exact contents may vary as the project evolves.

---

# 🔄 How It Works

When a user submits symptoms:

### 1. Symptom Input

The user describes their symptoms through the frontend.

```text
"I have fever, cough and difficulty breathing."
```

### 2. Disease Prediction

The symptoms are processed by the machine-learning pipeline.

The Random Forest classifier produces candidate diseases.

```text
Symptoms
   ↓
Feature processing
   ↓
Random Forest
   ↓
Candidate diseases
```

### 3. Knowledge Retrieval

Relevant information is retrieved from the medical knowledge base using ChromaDB.

```text
User Query
    ↓
Embedding
    ↓
ChromaDB
    ↓
Relevant medical information
```

### 4. AI Generation

The retrieved information and prediction context are provided to MedGemma.

```text
Disease candidates
       +
Retrieved context
       +
User symptoms
       ↓
    MedGemma
       ↓
AI-assisted response
```

### 5. Triage

The system evaluates the severity/urgency of the reported symptoms and provides appropriate guidance.

---

# 🔌 API

The backend exposes REST endpoints through FastAPI.

Once the backend is running, interactive API documentation is available at:

```text
http://localhost:8000/docs
```

You can use the Swagger interface to:

* View available endpoints
* Send requests
* Test predictions
* Inspect responses
* Understand request/response schemas

---

# 🐳 Docker Deployment

A production deployment can be structured as:

```text
                 Internet
                    │
                    ▼
             ┌─────────────┐
             │   Frontend  │
             │   Vercel    │
             └──────┬──────┘
                    │
                  HTTPS
                    │
                    ▼
             ┌─────────────┐
             │   FastAPI   │
             │   Backend   │
             └──────┬──────┘
                    │
          ┌─────────┼─────────┐
          ▼         ▼         ▼
      ChromaDB   ML Model   Ollama
                              │
                              ▼
                         MedGemma 4B
```

For GPU-based deployment, a GPU cloud provider such as RunPod can host the backend and Ollama/MedGemma together.

The frontend can be deployed independently to Vercel or another static hosting provider.

---

# 🖥️ Recommended Production Setup

For a public deployment:

| Component       | Recommended Hosting      |
| --------------- | ------------------------ |
| React frontend  | Vercel                   |
| FastAPI backend | GPU VPS / RunPod         |
| MedGemma        | Ollama on GPU server     |
| ChromaDB        | Backend server           |
| ML model        | Backend server           |
| HTTPS           | Reverse proxy / platform |

Only the **FastAPI API** should be exposed publicly.

Ollama should remain private behind the backend.

---

# 🧪 Development

Run the backend:

```bash
python run.py
```

Run the frontend:

```bash
cd frontend
npm run dev
```

For frontend production build:

```bash
npm run build
```

---

# 🩻 Example Workflow

```text
User:
"I have a persistent cough and fever."

             ↓

       Symptom Processing

             ↓

       Random Forest
       Disease Candidates

             ↓

          ChromaDB
      Medical Knowledge

             ↓

         MedGemma 4B

             ↓

      Severity / Triage

             ↓

     Contextual AI Response
```

---

# ⚠️ Medical Safety

MedAssist is intended for **research, experimentation, and educational purposes**.

It should not be used as:

* A replacement for a doctor
* A definitive diagnostic system
* A prescription system
* Emergency medical advice
* A substitute for professional medical evaluation

If someone is experiencing severe or life-threatening symptoms, they should contact local emergency medical services or a qualified healthcare professional.

---

# 🔒 Privacy

If running the complete inference pipeline locally with Ollama, model inference can remain on the local machine.

However, deployment configuration determines what data is transmitted between the frontend and backend.

When deploying publicly:

* Use HTTPS
* Avoid logging sensitive medical information
* Do not store unnecessary user data
* Protect backend endpoints
* Keep secrets outside the repository
* Restrict direct access to Ollama

---

# 🚧 Project Status

MedAssist is an **experimental AI/ML project** and is under active development.

Potential future improvements include:

* Better symptom extraction
* Improved medical knowledge retrieval
* More robust triage logic
* Better evaluation datasets
* Authentication and access control
* Observability and logging
* GPU-optimized inference
* Production-grade deployment
* Comprehensive medical safety evaluation

---

# 🤝 Contributing

Contributions are welcome.

### 1. Fork the repository

```bash
git fork https://github.com/safal999sapkota-collab/ARTEMIS-11.git
```

### 2. Create a branch

```bash
git checkout -b feature/your-feature
```

### 3. Make your changes

### 4. Commit

```bash
git add .
git commit -m "Add your feature"
```

### 5. Push

```bash
git push origin feature/your-feature
```

### 6. Open a Pull Request

---

# 📜 License

See the repository's license file for the applicable licensing terms.

---
---

## ⭐ Support

If you find this project useful, consider giving the repository a ⭐ on GitHub.

**
# MedBot
