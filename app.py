import re
import uuid
import os
import requests
from io import BytesIO
import pdfplumber
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader, PdfWriter
from storage import load_config, save_config

app = Flask(
    __name__,
    static_folder="public",
    static_url_path=""
)

# Categories that are protected (cannot be deleted)
BASE_CATEGORIES = frozenset({
    "NSAIDS, COXI",
    "Weak opioids",
    "Strong opioids",
    "Adjuvants / anti neuropathic pain",
    "Muscle relaxants"
})


# ─── Config Helpers ───────────────────────────────────────────────────────────

def build_entries_list(config: dict) -> list:
    entries = []
    for cat_name, cat_entries in config.items():
        for entry in cat_entries:
            terms = entry.get("search_terms", "").strip()
            if not terms:
                continue
            entries.append({
                "category": cat_name,
                "id": entry["id"],
                "search_terms": terms,
                "display_name": entry["display_name"],
                "is_base": entry.get("is_base", False),
            })
    return entries

def build_category_order(config: dict) -> list:
    order = [c for c in BASE_CATEGORIES if c in config]
    for c in config:
        if c not in order:
            order.append(c)
    return order

CATEGORY_ENTRIES = build_entries_list(load_config())


# ─── Detection & Hebrew Helpers ───────────────────────────────────────────────

def sanitize(text: str) -> str:
    return re.sub(r'[^A-Za-z]', ' ', text)

def clean_letters_only(text: str) -> str:
    return re.sub(r'[^a-z]', '', text.lower())

def fix_hebrew_visual_text(text: str) -> str:
    """Fixes visual-order Hebrew text extracted from PDFs where Hebrew words are reversed."""
    if not text:
        return text
    fixed_lines = []
    for line in text.split('\n'):
        words = line.split(' ')
        fixed_words = []
        for word in words:
            # If the word contains Hebrew characters, reverse its characters back to logical order
            if re.search(r'[\u0590-\u05FF]', word):
                fixed_words.append(word[::-1])
            else:
                fixed_words.append(word)
        fixed_lines.append(' '.join(fixed_words))
    return '\n'.join(fixed_lines)


# ─── OCR Helper ──────────────────────────────────────────────────────────────

def extract_text_with_ocr_api(pdf_stream) -> str:
    api_key = os.environ.get("OCR_API_KEY")
    if not api_key:
        print("OCR API key is missing. Cannot perform OCR fallback.")
        return ""

    pdf_stream.seek(0)
    try:
        reader = PdfReader(pdf_stream)
        total_pages = len(reader.pages)
    except Exception as e:
        print(f"Failed to read PDF for OCR chunking: {e}")
        return ""

    full_ocr_text = ""

    for i in range(0, total_pages, 3):
        writer = PdfWriter()
        chunk_pages = min(3, total_pages - i)
        
        for j in range(chunk_pages):
            writer.add_page(reader.pages[i + j])
            
        chunk_stream = BytesIO()
        writer.write(chunk_stream)
        chunk_stream.seek(0)
        chunk_bytes = chunk_stream.read()
        
        payload = {
            'apikey': api_key,
            'language': 'eng',
            'isOverlayRequired': False,
            'scale': True,
            'OCREngine': 1
        }
        
        try:
            print(f"Sending OCR request for pages {i+1} to {i+chunk_pages}...")
            response = requests.post(
                'https://api.ocr.space/parse/image',
                data=payload,
                files={'file': ('chunk.pdf', chunk_bytes, 'application/pdf')},
                timeout=50
            )
            result = response.json()
            
            if result.get('IsErroredOnProcessing'):
                print(f"OCR Error on chunk {i//3 + 1}: {result.get('ErrorMessage')}")
                continue
                
            for item in result.get('ParsedResults', []):
                full_ocr_text += item.get('ParsedText', '') + "\n"
                
        except Exception as e:
            print(f"OCR request failed on chunk {i//3 + 1}: {e}")
            
    return full_ocr_text


# ─── PDF Extraction ───────────────────────────────────────────────────────────

def extract_text_from_pdf(pdf_stream) -> str:
    # Tier 1: pdfplumber
    raw_text_lines = []
    try:
        pdf_stream.seek(0)
        with pdfplumber.open(pdf_stream) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                raw_text_lines.append(text)
        full_text = "\n".join(raw_text_lines)
        if len(full_text.strip()) >= 20:
            return fix_hebrew_visual_text(full_text)
    except Exception:
        pass

    # Tier 2: PyPDF2
    raw_text_lines = []
    try:
        pdf_stream.seek(0)
        reader = PdfReader(pdf_stream)
        for page in reader.pages:
            text = page.extract_text() or ""
            raw_text_lines.append(text)
        full_text = "\n".join(raw_text_lines)
        if len(full_text.strip()) >= 20:
            return fix_hebrew_visual_text(full_text)
    except Exception:
        pass

    # Tier 3: OCR API Fallback
    print("Standard extraction failed. Running OCR API fallback...")
    ocr_text = extract_text_with_ocr_api(pdf_stream)
    if len(ocr_text.strip()) >= 20:
        return fix_hebrew_visual_text(ocr_text)

    raise ValueError("The file format is not supported, contains no readable text, or OCR scanning failed.")


# ─── Drug Detection ───────────────────────────────────────────────────────────

def find_drugs_in_pdf(pdf_stream):
    full_text = extract_text_from_pdf(pdf_stream)
    config = load_config()
    cat_order = build_category_order(config)

    # יצירת טקסט נקי שבו כל התווים המיוחדים הופכים לרווחים, ומילים מופרדות כראוי
    sanitized_text = sanitize(full_text).lower()
    normalized_text = " ".join(sanitized_text.split())
    
    # רשימה של מילים בודדות ונקיות מסימני פיסוק (לצורך חיפוש תרופות במילה אחת)
    word_list = sanitized_text.split()
    word_list_clean = [clean_letters_only(w) for w in word_list if clean_letters_only(w)]

    results = {cat: [] for cat in cat_order}
    seen = {cat: set() for cat in cat_order}

    for entry in CATEGORY_ENTRIES:
        cat = entry["category"]
        display = entry["display_name"]

        terms = [t.strip() for t in re.split(r'[-–]', entry["search_terms"])]

        matched = False
        for term in terms:
            if not term:
                continue
                
            term_words = term.lower().split()
            
            if len(term_words) > 1:
                # טיפול במונחי חיפוש עם מספר מילים (כמו "ROKACET PLUS")
                multi_word_clean = " ".join([clean_letters_only(w) for w in term_words if clean_letters_only(w)])
                if multi_word_clean and multi_word_clean in normalized_text:
                    matched = True
                    break
            else:
                # טיפול במונח חיפוש של מילה אחת
                term_clean = clean_letters_only(term)
                if not term_clean:
                    continue
                    
                if len(term_clean) >= 4:
                    # אם המונח באורך 4 אותיות ומעלה - נבדוק אם הוא מהווה חלק ממילה בודדת קיימת (למשל fenta בתוך fentanyl)
                    # זה מונע את ההתנגשות הקודמת שבה fenta נמצא בחיבור המילים hal(f) (enta)ngled
                    if any(term_clean in word for word in word_list_clean):
                        matched = True
                        break
                else:
                    # מונח קצר במיוחד דורש התאמה מדויקת ומלאה (מילה שלמה) כדי למנוע זיהויי שווא
                    if term_clean in word_list_clean:
                        matched = True
                        break

        if matched and display not in seen[cat]:
            seen[cat].add(display)
            results[cat].append(display)

    ordered_results = {cat: results[cat] for cat in cat_order if results[cat]}
    return ordered_results, full_text


# ─── Page Routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return app.send_static_file("index.html")

@app.route('/medications')
def medications_page():
    return app.send_static_file("medications.html")


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.route('/api/medications', methods=['GET'])
def get_medications():
    config = load_config()
    return jsonify({"success": True, "categories": config})

@app.route('/api/categories', methods=['POST'])
def add_category():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Category name is required"}), 400

    config = load_config()
    if name in config:
        return jsonify({"success": False, "error": f"Category '{name}' already exists"}), 409

    config[name] = []
    save_config(config)

    global CATEGORY_ENTRIES
    CATEGORY_ENTRIES = build_entries_list(config)

    return jsonify({"success": True, "category": name}), 201

@app.route('/api/categories/<path:name>', methods=['DELETE'])
def delete_category(name):
    if name in BASE_CATEGORIES:
        return jsonify({"success": False, "error": "Base categories cannot be deleted"}), 403

    config = load_config()
    if name not in config:
        return jsonify({"success": False, "error": f"Category '{name}' not found"}), 404

    del config[name]
    save_config(config)

    global CATEGORY_ENTRIES
    CATEGORY_ENTRIES = build_entries_list(config)

    return jsonify({"success": True})

@app.route('/api/medications', methods=['POST'])
def add_medication():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON body"}), 400

    category = data.get("category", "").strip()
    search_terms = data.get("search_terms", "").strip()
    display_name = data.get("display_name", "").strip()

    if not category or not search_terms or not display_name:
        return jsonify({"success": False, "error": "category, search_terms, and display_name are required"}), 400

    config = load_config()
    if category not in config:
        return jsonify({"success": False, "error": f"Category '{category}' does not exist"}), 400

    new_entry = {
        "id": str(uuid.uuid4()),
        "search_terms": search_terms,
        "display_name": display_name,
        "is_base": False
    }
    config[category].append(new_entry)
    save_config(config)

    global CATEGORY_ENTRIES
    CATEGORY_ENTRIES = build_entries_list(config)

    return jsonify({"success": True, "entry": new_entry}), 201

@app.route('/api/medications/<drug_id>', methods=['DELETE'])
def delete_medication(drug_id):
    config = load_config()
    for category, entries in config.items():
        for entry in entries:
            if entry["id"] == drug_id:
                if entry.get("is_base", False):
                    return jsonify({"success": False, "error": "Base medications cannot be deleted"}), 403
                entries.remove(entry)
                save_config(config)

                global CATEGORY_ENTRIES
                CATEGORY_ENTRIES = build_entries_list(config)
                return jsonify({"success": True})

    return jsonify({"success": False, "error": "Medication not found"}), 404


# ─── Upload Route ─────────────────────────────────────────────────────────────

@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400

    file = request.files['pdf_file']
    if not file or not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400

    try:
        results, raw_text = find_drugs_in_pdf(file.stream)
        return jsonify({
            'success': True,
            'results': results,
            'raw_text': raw_text
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)