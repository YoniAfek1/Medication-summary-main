# Medication Summary - Project Guidelines & Tasks

## 🎯 Project Context
This is a local Python web application built with Flask and Vanilla JavaScript. 
Its purpose is to extract text from medical PDF documents and automatically detect specific pain medications based on predefined categories, using strict string matching and Regular Expressions.

## ⚠️ STRICT RULES (READ BEFORE CODING)
1. **NO LLMs FOR LOGIC:** This system is a deterministic automation tool. You are strictly forbidden from integrating any LLM APIs (OpenAI, Anthropic, etc.) into the application logic to read or summarize the PDFs. The text extraction and drug detection must remain 100% algorithmic (RegEx, string matching, etc.).
2. **Tech Stack:** Keep the frontend in Vanilla HTML/CSS/JS. Do not introduce React, Vue, or other frontend frameworks. Backend is Flask.
3. **Language:** All UI text, instructions, headers, and buttons across the entire application must be strictly in **English** (keep the phrasing simple, friendly, and clear).

## 🎨 UI/UX & Design Guidelines
* **Consistent Styling:** Both the main upload page and the new Medications Management page must share the exact same design language, CSS styles, color scheme, and layout structure. 
* **Navigation:** You must add clear, user-friendly navigation buttons (or a simple navigation bar) on both pages to allow users to easily switch back and forth between the Home Page (`/`) and the Medications Page (`/medications`).

---

## 🚀 UPGRADE PLAN (Current Missions)

Please execute the following upgrades step-by-step. Present a plan for each step before writing the code.

### Mission 1: Dual-Tier PDF Text Extraction
**Problem:** The current extraction method needs to be more robust, falling back to an alternative library if the primary one fails.
**Task:** 
* Implement a two-tier extraction pipeline directly in the application logic:
  * **Tier 1 (Primary):** Use `pdfplumber` to extract text from the PDF.
  * **Tier 2 (Fallback):** If `pdfplumber` extracts fewer than 20 characters, automatically fall back to using `PyPDF2` (or `pypdf`) to extract the text.
  * **Failure Handling:** If both methods fail (the final extracted text still contains fewer than 20 characters), stop the processing and return a clear error message to the frontend stating that "The file format is not supported or contains no readable text."
* Update `requirements.txt` to include `pdfplumber`. 

### Mission 2: Medications Management Interface (New Page)
**Problem:** The drug categories are hardcoded, and users have no visibility or control over what is being searched.
**Task:** 
* Create a new route and frontend page (e.g., `/medications`) to serve as a transparency and management dashboard.
* **UI Layout:** Render a distinct, clean table for each drug category (e.g., "Weak opioids", "Strong opioids").
* **Table Structure:** Each table must have exactly two columns:
  1. `Search Term(s)` (The string or RegEx used to search the text).
  2. `Display Name` (The output name shown to the user upon a match).
* **CRUD Functionality:** 
  * Users must be able to ADD new medications (Search Term and Display Name) to any category.
  * Users must be able to DELETE medications.
* **CRITICAL CONSTRAINT - Protect Base Drugs:** The existing medications currently hardcoded in `app.py` are the "stable base". They must be visibly marked and **cannot be deleted** by the user. Only newly added, user-generated medications can be deleted. 
* **Implementation Hint:** You will likely need to refactor how drugs are stored (e.g., using a local JSON database like `drugs_config.json`) with a boolean flag like `is_base: true` to prevent deletion of core items.
* **Dynamic Categories:** Categories are now fully managed via `drugs_config.json` (local dev) or Vercel KV / Redis (production). Users can create new categories through the `/medications` page UI (`POST /api/categories`). Newly created categories are automatically available in the PDF detection pipeline — any medications added to them will be searched for when a PDF is uploaded. The category ordering on the medications page shows the known base categories first, followed by any user-created dynamic categories.
* **Delete Category:** User-created categories can be deleted via the red "✕ Delete Category" button in the category header on the `/medications` page. The 5 base categories (NSAIDS, COXI; Weak opioids; Strong opioids; Adjuvants; Muscle relaxants) are strictly protected and cannot be deleted.

## 🗄️ Vercel Persistence (Storage Layer)
The application stores medication data (categories, entries) in `drugs_config.json` for local development. When deployed on Vercel, the ephemeral filesystem makes this unreliable. The app uses a `storage.py` module that supports two backends:

* **Local (default):** reads/writes `drugs_config.json` directly
* **Redis (production):** when the `KV_URL` environment variable is set, automatically connects to Vercel KV (or any Redis instance) and keeps the config there

### To enable Vercel KV persistence:
1. In your Vercel dashboard: **Storage → Create a KV database**
2. Copy the `KV_URL` connection string
3. Add it as an environment variable `KV_URL` in your Vercel project settings
4. Redeploy — the app auto-detects `KV_URL` and switches to Redis

> **Note:** If Redis is empty (first deploy), `storage.py` seeds it from the local `drugs_config.json` bundled in the deployment.
