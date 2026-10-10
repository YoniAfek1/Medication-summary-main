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

## ✅ IMPLEMENTED CAPABILITIES & FEATURES
The following core capabilities have been successfully implemented in the system:

### 1. Robust PDF Text Extraction
* **Tier 1 (Primary):** Uses `pdfplumber` for robust standard text extraction.
* **Tier 2 (Fallback):** If `pdfplumber` fails or extracts fewer than 20 characters, it falls back to `PyPDF2`.
* **Tier 3 (OCR Fallback):** Integrates an external OCR API to process scanned documents or images if standard extraction fails.
* **Hebrew Fixer:** Automatically detects and reverses visual-order Hebrew text extracted from PDFs into logical order.

### 2. Smart Drug Detection (Regex & Word Boundaries)
* Prevents "false positives" by strictly enforcing word boundaries for short terms (1-3 letters).
* Allows substring matches only for longer terms (4+ letters) within bounded words.
* Supports exact multi-word matching (e.g., "ROKACET PLUS") using sanitized text.

### 3. Maximum Dosage Extraction
* Automatically extracts the highest dosage taken for a detected medication across the entire document.
* **Supported Units:** `mg`, `ml`, `gm`, `g`.
* **Logic:** Uses a Two-Pass Regex approach. Scans up to 3 words (distance of up to 2 words) immediately following a detected drug name to accurately capture its dosage.
* **Conflict Resolution:** If the exact same drug is found with different units in the same document (e.g., `10GM` and `20MG`), it safely skips displaying the dosage to avoid medical inaccuracies.
* **Output Format:** Appends "Maximum dosage {value}{unit}" directly to the display name.

### 4. Medications Management Dashboard (`/medications`)
* Dynamic CRUD interface to manage drugs per category.
* **Protected Base:** Core medications and 5 core categories (e.g., NSAIDS, Weak opioids) are protected and cannot be deleted.
* Users can dynamically add and delete custom categories and user-generated medications. 

### 5. Seamless "Copy to Clipboard"
* A dedicated UI button on the main dashboard to copy the extraction summary.
* **Data-Driven Approach:** Builds the clipboard text directly from the JSON response object (bypassing DOM scraping), ensuring clean, plain-text formatting that pastes perfectly into Microsoft Word.

---

## 🗄️ Vercel Persistence (Storage Layer)
The application stores medication data (categories, entries) in `drugs_config.json` for local development. When deployed on Vercel, the ephemeral filesystem makes this unreliable. The app uses a `storage.py` module that supports two backends:

* **Local (default):** reads/writes `drugs_config.json` directly.
* **Redis (production):** when the `KV_URL` environment variable is set, automatically connects to Vercel KV (or any Redis instance) and keeps the config there.

### To enable Vercel KV persistence:
1. In your Vercel dashboard: **Storage → Create a KV database**
2. Copy the `KV_URL` connection string
3. Add it as an environment variable `KV_URL` in your Vercel project settings
4. Redeploy — the app auto-detects `KV_URL` and switches to Redis

> **Note:** If Redis is empty (first deploy), `storage.py` seeds it from the local `drugs_config.json` bundled in the deployment.