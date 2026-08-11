# pdf_ingestion_ocr.py
import fitz  # PyMuPDF
import re
import sqlite3
import pytesseract
from pdf2image import convert_from_path

def process_catalog_ocr(pdf_path, brand_name, category_name, db_name="master_products.db"):
    print(f"Processing catalog via OCR: {pdf_path}...")
    
    # 1. First attempt standard text extraction
    doc = fitz.open(pdf_path)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    code_pattern = re.compile(
        r'\b([A-Z0-9]{2,5}-[A-Z0-9-]{3,18}|[SFEABSP][0-9]{7,8}[A-Z0-9]*|Cat\.\s*No\.?\s*:\s*[A-Z0-9]+|[F][0-9]{8,10}[A-Z0-9]*)\b',
        re.IGNORECASE
    )
    price_pattern = re.compile(r'(?:MRP|₹|Rs\.?|`)\s*:?\s*([0-9,]{3,7})', re.IGNORECASE)

    extracted_count = 0

    for page_num in range(len(doc)):
        text = doc[page_num].get_text("text")
        
        # Fallback to OCR if page has image layers without plain text
        if not text or len(text.strip()) < 50:
            images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1, dpi=200)
            if images:
                text = pytesseract.image_to_string(images[0])

        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for i, line in enumerate(lines):
            c_match = code_pattern.search(line)
            p_match = price_pattern.search(line)

            if c_match or p_match:
                window = lines[max(0, i - 3):min(len(lines), i + 4)]
                block = " ".join(window)

                found_code = c_match.group(1) if c_match else None
                found_price = p_match.group(1) if p_match else None

                if not found_code:
                    m = code_pattern.search(block)
                    if m:
                        found_code = m.group(1)

                if not found_price:
                    m = price_pattern.search(block)
                    if m:
                        found_price = m.group(1)

                if found_code and found_price:
                    clean_code = found_code.replace("Cat. No.", "").replace(":", "").strip().upper()
                    try:
                        clean_price = float(found_price.replace(',', ''))
                    except ValueError:
                        continue

                    desc_lines = [cl for cl in window if clean_code not in cl.upper() and found_price not in cl and len(cl) > 3]
                    clean_desc = " ".join(desc_lines[:2]).strip()

                    cursor.execute('''
                        INSERT OR REPLACE INTO products (brand, category, sku_cat_no, mrp_inr, description, page_no, source_file)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (brand_name, category_name, clean_code, clean_price, clean_desc, page_num + 1, pdf_path))
                    extracted_count += 1

    conn.commit()
    conn.close()
    print(f"Finished {pdf_path}: Ingested {extracted_count} items.")

# Batch Ingest All 5 Catalogs:
# process_catalog_ocr("ESSCO 2.6 Catalogue-updated.pdf", "ESSCO", "Sanitaryware & Bathware")
# process_catalog_ocr("CERA LUXE Catalogue May 2026.pdf", "CERA LUXE", "Sanitaryware & Bathware")
# process_catalog_ocr("CERA Look Book May 2026.pdf", "CERA", "Sanitaryware")
# process_catalog_ocr("Unboxing Catalogue July 2026.pdf", "CERA Luxe", "Faucets & Fittings")
# process_catalog_ocr("Interactive Fan Catalogue 2026.pdf", "Orient Electric", "Electrical Fans")