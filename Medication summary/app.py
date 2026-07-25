import re
from io import BytesIO
from flask import Flask, request, jsonify
from PyPDF2 import PdfReader

app = Flask(
    __name__,
    static_folder="public",
    static_url_path=""
)

# 1. Category → list of full entries
DRUG_CATEGORIES = {
    "Weak opioids": [
        "ROKACET - ROKACET PLUS",
        "ZALDIAR",
        "TRAMADEX - TRAMADOL - Tramal",
        "BUTRANS - BUPERNORPHINE"
    ],
    "Strong opioids": [
        "PERCOCET - OXYCODONE",
        "TARGIN - OXYCODONE",
        "OXYCONTIN – OXYCODONE",
        "OXYCOD SYRUP",
        "FENTANYL - fenta- fentadol",
        "MORPHINE - MCR - MIR"
    ],
    "Adjuvants / anti neuropathic pain": [
        "LYRICA - PREGABALIN",
        "GABAPENTIN - neurontin",
        "CYMBALTA - DULOXETINE - dulox",
        "VENLAFAXINE - VIEPAX - venla",
        "ELATROL - AMITRIPTYLINE - elatrolet",
        "NORTYLIN - NORTRIPTYLINE",
        "IXEL - MILNACIPRAN",
        "TEGRETOL - CARBAMAZEPINE - teril -",
        "TRILEPTIN – OXCARBAZEPINE - trileptal - trexapin - timonil- carbi "
    ],
    "Muscle relaxants": [
        "MUSCOL",
        "BACLOSAL – BACLOFEN",
        "DANTRIUM – DANTROLENE"
    ]
}

def sanitize(text: str) -> str:
    return re.sub(r'[^A-Za-z]', ' ', text)

def clean_letters_only(text: str) -> str:
    return re.sub(r'[^a-z]', '', text.lower())

def find_drugs_in_pdf(pdf_stream):
    reader = PdfReader(pdf_stream)
    results = {cat: [] for cat in DRUG_CATEGORIES}
    raw_text_lines = []

    nsaids_terms = [
        "ARCOXIA", "ETORICOXIB", "CELCOX", "CELECOXIB", "IBUPROFEN", "NUROFEN", "COMBODEX", "Advil",
        "Etopan", "Etodalac", "Voltaren", "Abitren", "Diclofenac", "brexin", "indomethacin", "naxin",
        "naproxen", "piroxicam", "point"
    ]

    # extract raw text
    full_text = ""
    for page in reader.pages:
        text = page.extract_text() or ""
        raw_text_lines.append(text)
        full_text += text + "\n"

    # prepare versions of text
    sanitized_text = sanitize(full_text).lower()
    cleaned_text = clean_letters_only(full_text)
    word_list = sanitized_text.split()
    word_list_clean = [clean_letters_only(w) for w in word_list]

    # detect NSAIDS
    found_nsaids = False
    for term in nsaids_terms:
        term_clean = clean_letters_only(term)
        if len(term_clean) >= 4:
            if term_clean in cleaned_text:
                found_nsaids = True
                break
        else:
            if term_clean in word_list_clean:
                found_nsaids = True
                break
    results["NSAIDS, COXI"] = ["NSAIDS, COXI"] if found_nsaids else []

    # detect drug categories
    for category, entries in DRUG_CATEGORIES.items():
        if category == "NSAIDS, COXI":
            continue
        for full_entry in entries:
            synonyms = [s.strip() for s in re.split(r'[-–]', full_entry)]
            for synonym in synonyms:
                term_clean = clean_letters_only(synonym)
                if not term_clean:
                    continue
                if len(term_clean) >= 4:
                    if term_clean in cleaned_text:
                        if full_entry not in results[category]:
                            results[category].append(full_entry)
                        break
                else:
                    if term_clean in word_list_clean:
                        if full_entry not in results[category]:
                            results[category].append(full_entry)
                        break

    output_order = [
        "NSAIDS, COXI",
        "Weak opioids",
        "Strong opioids",
        "Adjuvants / anti neuropathic pain",
        "Muscle relaxants"
    ]
    ordered_results = {cat: results[cat] for cat in output_order if results[cat]}
    raw_text = "\n".join(raw_text_lines)
    return ordered_results, raw_text

@app.route('/')
def index():
    return app.send_static_file("index.html")

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

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
