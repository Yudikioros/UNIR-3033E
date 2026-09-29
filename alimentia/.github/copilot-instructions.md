# Copilot Instructions for UNIR-3033E

This document serves as a comprehensive guide for future Copilot sessions, providing high-level architectural context, core conventions, and primary command patterns for working effectively in the `alimentia` repository.

## 🚀 High-Level Architecture

The application follows a modern decoupled architecture:

1.  **Frontend (Client):** The user interface is built with **Next.js (React/TypeScript)**. It is responsible for rendering the UI and handling client-side state. Key components are located in `alimentia/frontend/src/app`.
2.  **Backend (API):** The core business logic is exposed via a **FastAPI** backend. This service handles data processing, authentication, and communication with external knowledge bases.
3.  **Data Flow:**
    *   **Relational Data:** Patient and Diet Plan metadata are managed using **Prisma ORM** against a local **SQLite** database (`alimentia/data/db/alimentia.db`).
    *   **Knowledge Retrieval (RAG):** Medical guidelines and source documents are stored and queried using **Qdrant** (a vector database). This is integrated via `llama-index-core`, allowing the backend to perform Retrieval-Augmented Generation (RAG) for contextual information.
    *   **Process:** User interaction $\rightarrow$ Next.js $\rightarrow$ FastAPI $\rightarrow$ (Prisma for records OR LlamaIndex/Qdrant for knowledge) $\rightarrow$ Response.

## 🛠️ Build, Test, and Lint Commands

These commands assume the root directory of the repository is the current working directory.

### 🟢 Frontend (Next.js)
*   **Run Development Server:** `npm run dev`
*   **Build for Production:** `npm run build`
*   **Linting:** (Check `package.json` for specific ESLint commands, e.g., `npm run lint`)

### 🔵 Backend (FastAPI/Python)
*   **Install Dependencies:** Use `uv` (or `pip`): `uv sync` (or `pip install -r backend/requirements.txt` if a requirements file existed).
*   **Run Development Server:** `uvicorn alimentia.backend.main:app --reload` (Adjust `main:app` based on actual entry point).
*   **Running Tests:** Execute tests using the standard Python test runner (e.g., `pytest` or similar framework command). *Note: No specific test command was found, please verify the testing framework.*

## 💡 Key Conventions & Patterns

*   **Environment Variables:** Secrets and configuration should be handled via a `.env` file or the `python-dotenv` library.
*   **Prisma Schema:** All primary data models (`Patient`, `DietPlan`) and their relationships are defined and managed through `alimentia/backend/schema.prisma`. Changes here require running Prisma migrations.
*   **LlamaIndex/RAG:** Vector store operations are centralized. Document loading and embedding are managed by the `llama-index-core` library, utilizing Qdrant for efficient similarity searches.
*   **Path Management:** The application is split into `alimentia/frontend/` and `alimentia/backend/`. Python dependencies are isolated in `alimentia/backend/.venv/`.

## 🚨 Quick References

*   **Database Schema:** `alimentia/backend/schema.prisma`
*   **Core FastAPI Code:** Look for the main FastAPI router and startup files in `alimentia/backend/` or `alimentia/backend/src/`.
*   **TypeScript/Next.js:** Primary pages and components are in `alimentia/frontend/src/app`.
