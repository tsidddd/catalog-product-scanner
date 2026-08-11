from fastapi import FastAPI, Query, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import pytesseract
from PIL import Image
import io
import re
import requests

app = FastAPI(title="Cloud Catalog Product Scanner API")

# Enable CORS for phone and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Google Sheets Webhook Configuration
# -------------------------------------------------------------------
# Paste your deployed Google Apps Script URL below:
GOOGLE_SHEET_WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbyNBzXCgogYweXJk6UH40hnvGe_cQ4GVjzLthLkYj0SZ4J3aUTo_W-fZ18K2JDx08s4/exec"


# -------------------------------------------------------------------
# Helper Functions
# -------------------------------------------------------------------
def query_db_sku(clean_sku: str):
    """
    Queries the SQLite database for a product.
    Prioritizes EXACT SKU matches first to avoid returning similar variants.
    """
    conn = sqlite3.connect("master_products.db")
    cursor = conn.cursor()

    # 1. Try EXACT match first
    cursor.execute("""
        SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(sku_cat_no) = ?
    """, (clean_sku,))
    results = cursor.fetchall()

    # 2. Fall back to LIKE wildcard search only if exact match returns nothing
    if not results:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE UPPER(sku_cat_no) LIKE ?
            LIMIT 1
        """, (f"%{clean_sku}%",))
        results = cursor.fetchall()

    conn.close()
    return results


def log_to_google_sheet(brand: str, category: str, sku: str, mrp: str, desc: str, scan_type: str = "Phone Photo"):
    """
    Sends scanned item metadata (including category) to Google Sheets via Apps Script Webhook.
    """
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"):
        try:
            payload = {
                "brand": brand,
                "category": category,
                "sku": sku,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=3)
        except Exception as e:
            print(f"Google Sheet Logging Error: {e}")


def clean_description(desc_raw: str) -> str:
    """
    Removes footer noise (e.g. 'esscobathware.com | 154') from catalog descriptions.
    """
    if not desc_raw:
        return ""
    cleaned = re.sub(r'esscobathware\.com\s*\|\s*\d+', '', desc_raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# -------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------
@app.get("/")
def home():
    """
    Root route providing a status message and link to live documentation.
    """
    return {
        "status": "online",
        "service": "Catalog Product Scanner API",
        "interactive_docs": "/docs",
        "search_endpoint": "/scan?sku=AEC-1111N"
    }


@app.get("/scan")
def scan_text_sku(sku: str = Query(..., description="Target SKU or Cat. No.")):
    """
    Searches the catalog database by exact/partial SKU string.
    """
    clean_sku = sku.strip().upper()
    results = query_db_sku(clean_sku)

    if results:
        items = []
        for r in results:
            cleaned_desc = clean_description(r[4])
            items.append({
                "brand": r[0],
                "category": r[1],
                "sku_cat_no": r[2],
                "mrp_inr": f"₹{r[3]:,.2f}",
                "description": cleaned_desc,
                "page_no": r[5],
                "source_catalog": r[6]
            })

        # Log ONLY the primary top match to Google Sheets to prevent duplicate rows
        top_match = items[0]
        log_to_google_sheet(
            brand=top_match["brand"],
            category=top_match["category"],
            sku=top_match["sku_cat_no"],
            mrp=top_match["mrp_inr"],
            desc=top_match["description"],
            scan_type="Manual Text Search"
        )

        return {"status": "success", "count": len(items), "products": items}
    else:
        raise HTTPException(status_code=404, detail=f"No product found matching SKU: '{sku}'")


@app.post("/scan-image")
async def scan_uploaded_image(file: UploadFile = File(...)):
    """
    Processes an uploaded product photo using OCR to detect printed SKUs or Cat. Nos.
    """
    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file provided.")

    # Execute Tesseract OCR on the image
    ocr_text = pytesseract.image_to_string(image)

    # Regex search for candidate SKU patterns
    sku_pattern = re.compile(r'\b([A-Z0-9]{2,5}-[A-Z0-9-]{3,18}|[SFEABSP][0-9]{7,8}[A-Z0-9]*)\b', re.IGNORECASE)
    matches = sku_pattern.findall(ocr_text)

    for candidate in matches:
        clean_candidate = candidate.strip().upper()
        results = query_db_sku(clean_candidate)

        if results:
            r = results[0]
            cleaned_desc = clean_description(r[4])
            mrp_str = f"₹{r[3]:,.2f}"

            # Log detected product to Google Sheets with category
            log_to_google_sheet(
                brand=r[0],
                category=r[1],
                sku=r[2],
                mrp=mrp_str,
                desc=cleaned_desc,
                scan_type="Camera Photo OCR"
            )

            return {
                "status": "success",
                "detected_sku": clean_candidate,
                "products": [{
                    "brand": r[0],
                    "category": r[1],
                    "sku_cat_no": r[2],
                    "mrp_inr": mrp_str,
                    "description": cleaned_desc,
                    "page_no": r[5],
                    "source_catalog": r[6]
                }]
            }

    raise HTTPException(status_code=404, detail="No recognized product SKU detected in the image.")    cursor = conn.cursor()

    # 1. Try EXACT match first
    cursor.execute("""
        SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(sku_cat_no) = ?
    """, (clean_sku,))
    results = cursor.fetchall()

    # 2. Fall back to LIKE wildcard search only if exact match returns nothing
    if not results:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE UPPER(sku_cat_no) LIKE ?
            LIMIT 1
        """, (f"%{clean_sku}%",))
        results = cursor.fetchall()

    conn.close()
    return results


def log_to_google_sheet(brand: str, category: str, sku: str, mrp: str, desc: str, scan_type: str = "Phone Photo"):
    """
    Sends scanned item metadata (including category) to Google Sheets via Apps Script Webhook.
    """
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"):
        try:
            payload = {
                "brand": brand,
                "category": category,
                "sku": sku,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=3)
        except Exception as e:
            print(f"Google Sheet Logging Error: {e}")


def clean_description(desc_raw: str) -> str:
    """
    Removes footer noise (e.g. 'esscobathware.com | 154') from catalog descriptions.
    """
    if not desc_raw:
        return ""
    cleaned = re.sub(r'esscobathware\.com\s*\|\s*\d+', '', desc_raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# -------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------
@app.get("/")
def home():
    """
    Root route providing a status message and link to live documentation.
    """
    return {
        "status": "online",
        "service": "Catalog Product Scanner API",
        "interactive_docs": "/docs",
        "search_endpoint": "/scan?sku=AEC-1111N"
    }


@app.get("/scan")
def scan_text_sku(sku: str = Query(..., description="Target SKU or Cat. No.")):
    """
    Searches the catalog database by exact/partial SKU string.
    """
    clean_sku = sku.strip().upper()
    results = query_db_sku(clean_sku)

    if results:
        items = []
        for r in results:
            cleaned_desc = clean_description(r[4])
            items.append({
                "brand": r[0],
                "category": r[1],
                "sku_cat_no": r[2],
                "mrp_inr": f"₹{r[3]:,.2f}",
                "description": cleaned_desc,
                "page_no": r[5],
                "source_catalog": r[6]
            })

        # Log ONLY the primary top match to Google Sheets to prevent duplicate rows
        top_match = items[0]
        log_to_google_sheet(
            brand=top_match["brand"],
            category=top_match["category"],
            sku=top_match["sku_cat_no"],
            mrp=top_match["mrp_inr"],
            desc=top_match["description"],
            scan_type="Manual Text Search"
        )

        return {"status": "success", "count": len(items), "products": items}
    else:
        raise HTTPException(status_code=404, detail=f"No product found matching SKU: '{sku}'")


@app.post("/scan-image")
async def scan_uploaded_image(file: UploadFile = File(...)):
    """
    Processes an uploaded product photo using OCR to detect printed SKUs or Cat. Nos.
    """
    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file provided.")

    # Execute Tesseract OCR on the image
    ocr_text = pytesseract.image_to_string(image)

    # Regex search for candidate SKU patterns
    sku_pattern = re.compile(r'\b([A-Z0-9]{2,5}-[A-Z0-9-]{3,18}|[SFEABSP][0-9]{7,8}[A-Z0-9]*)\b', re.IGNORECASE)
    matches = sku_pattern.findall(ocr_text)

    for candidate in matches:
        clean_candidate = candidate.strip().upper()
        results = query_db_sku(clean_candidate)

        if results:
            r = results[0]
            cleaned_desc = clean_description(r[4])
            mrp_str = f"₹{r[3]:,.2f}"

            # Log detected product to Google Sheets with category
            log_to_google_sheet(
                brand=r[0],
                category=r[1],
                sku=r[2],
                mrp=mrp_str,
                desc=cleaned_desc,
                scan_type="Camera Photo OCR"
            )

            return {
                "status": "success",
                "detected_sku": clean_candidate,
                "products": [{
                    "brand": r[0],
                    "category": r[1],
                    "sku_cat_no": r[2],
                    "mrp_inr": mrp_str,
                    "description": cleaned_desc,
                    "page_no": r[5],
                    "source_catalog": r[6]
                }]
            }

    raise HTTPException(status_code=404, detail="No recognized product SKU detected in the image.")    cursor = conn.cursor()

    # 1. Try EXACT match first
    cursor.execute("""
        SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
        FROM products 
        WHERE UPPER(sku_cat_no) = ?
    """, (clean_sku,))
    results = cursor.fetchall()

    # 2. Fall back to LIKE wildcard search only if exact match returns nothing
    if not results:
        cursor.execute("""
            SELECT brand, category, sku_cat_no, mrp_inr, description, page_no, source_file 
            FROM products 
            WHERE UPPER(sku_cat_no) LIKE ?
            LIMIT 1
        """, (f"%{clean_sku}%",))
        results = cursor.fetchall()

    conn.close()
    return results


def log_to_google_sheet(brand: str, category: str, sku: str, mrp: str, desc: str, scan_type: str = "Phone Photo"):
    """
    Sends scanned item metadata (including category) to Google Sheets via Apps Script Webhook.
    """
    if "YOUR_COPIED" not in GOOGLE_SHEET_WEBHOOK_URL and GOOGLE_SHEET_WEBHOOK_URL.startswith("http"):
        try:
            payload = {
                "brand": brand,
                "category": category,
                "sku": sku,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }
            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json=payload, timeout=3)
        except Exception as e:
            print(f"Google Sheet Logging Error: {e}")


def clean_description(desc_raw: str) -> str:
    """
    Removes footer noise (e.g. 'esscobathware.com | 154') from catalog descriptions.
    """
    if not desc_raw:
        return ""
    cleaned = re.sub(r'esscobathware\.com\s*\|\s*\d+', '', desc_raw, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# -------------------------------------------------------------------
# API Endpoints
# -------------------------------------------------------------------
@app.get("/")
def home():
    """
    Root route providing a status message and link to live documentation.
    """
    return {
        "status": "online",
        "service": "Catalog Product Scanner API",
        "interactive_docs": "/docs",
        "search_endpoint": "/scan?sku=AEC-1111N"
    }


@app.get("/scan")
def scan_text_sku(sku: str = Query(..., description="Target SKU or Cat. No.")):
    """
    Searches the catalog database by exact/partial SKU string.
    """
    clean_sku = sku.strip().upper()
    results = query_db_sku(clean_sku)

    if results:
        items = []
        for r in results:
            cleaned_desc = clean_description(r[4])
            items.append({
                "brand": r[0],
                "category": r[1],
                "sku_cat_no": r[2],
                "mrp_inr": f"₹{r[3]:,.2f}",
                "description": cleaned_desc,
                "page_no": r[5],
                "source_catalog": r[6]
            })

        # Log ONLY the primary top match to Google Sheets to prevent duplicate rows
        top_match = items[0]
        log_to_google_sheet(
            brand=top_match["brand"],
            category=top_match["category"],
            sku=top_match["sku_cat_no"],
            mrp=top_match["mrp_inr"],
            desc=top_match["description"],
            scan_type="Manual Text Search"
        )

        return {"status": "success", "count": len(items), "products": items}
    else:
        raise HTTPException(status_code=404, detail=f"No product found matching SKU: '{sku}'")


@app.post("/scan-image")
async def scan_uploaded_image(file: UploadFile = File(...)):
    """
    Processes an uploaded product photo using OCR to detect printed SKUs or Cat. Nos.
    """
    contents = await file.read()
    try:
        image = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file provided.")

    # Execute Tesseract OCR on the image
    ocr_text = pytesseract.image_to_string(image)

    # Regex search for candidate SKU patterns
    sku_pattern = re.compile(r'\b([A-Z0-9]{2,5}-[A-Z0-9-]{3,18}|[SFEABSP][0-9]{7,8}[A-Z0-9]*)\b', re.IGNORECASE)
    matches = sku_pattern.findall(ocr_text)

    for candidate in matches:
        clean_candidate = candidate.strip().upper()
        results = query_db_sku(clean_candidate)

        if results:
            r = results[0]
            cleaned_desc = clean_description(r[4])
            mrp_str = f"₹{r[3]:,.2f}"

            # Log detected product to Google Sheets with category
            log_to_google_sheet(
                brand=r[0],
                category=r[1],
                sku=r[2],
                mrp=mrp_str,
                desc=cleaned_desc,
                scan_type="Camera Photo OCR"
            )

            return {
                "status": "success",
                "detected_sku": clean_candidate,
                "products": [{
                    "brand": r[0],
                    "category": r[1],
                    "sku_cat_no": r[2],
                    "mrp_inr": mrp_str,
                    "description": cleaned_desc,
                    "page_no": r[5],
                    "source_catalog": r[6]
                }]
            }

    raise HTTPException(status_code=404, detail="No recognized product SKU detected in the image.")            requests.post(GOOGLE_SHEET_WEBHOOK_URL, json={
                "brand": brand,
                "category": category,
                "sku": sku,
                "mrp": mrp,
                "description": desc,
                "scan_type": scan_type
            }, timeout=3)
        except Exception as e:
            print("Google Sheet Logging Error:", e)

@app.get("/scan")
def scan_text_sku(sku: str = Query(...)):
    clean_sku = sku.strip().upper()
    results = query_db_sku(clean_sku)
    
    if results:
        items = []
        for r in results:
            brand_name = r[0]
            cat_name = r[1]
            sku_code = r[2]
            mrp_formatted = f"₹{r[3]:,.2f}"
            description_text = r[4]
            page_number = r[5]
            catalog_file = r[6]
            
            items.append({
                "brand": brand_name,
                "category": cat_name,
                "sku_cat_no": sku_code,
                "mrp_inr": mrp_formatted,
                "description": description_text,
                "page_no": page_number,
                "source_catalog": catalog_file
            })
            
            # Log to Google Sheet with Category
            log_to_google_sheet(brand_name, cat_name, sku_code, mrp_formatted, description_text, "Manual Text Scan")
            
        return {"status": "success", "products": items}
    else:
        raise HTTPException(status_code=404, detail=f"No item found for '{sku}'")

@app.post("/scan-image")
async def scan_uploaded_image(file: UploadFile = File(...)):
    contents = await file.read()
    image = Image.open(io.BytesIO(contents))
    
    # Run OCR on the image
    ocr_text = pytesseract.image_to_string(image)
    
    # Extract candidate SKU patterns (e.g. AEC-1111N, S1013265VS, F1021451FG)
    sku_pattern = re.compile(r'\b([A-Z0-9]{2,5}-[A-Z0-9-]{3,18}|[SFEABSP][0-9]{7,8}[A-Z0-9]*)\b', re.IGNORECASE)
    matches = sku_pattern.findall(ocr_text)
    
    for candidate in matches:
        clean_candidate = candidate.strip().upper()
        results = query_db_sku(clean_candidate)
        if results:
            r = results[0]
            brand_name = r[0]
            cat_name = r[1]
            sku_code = r[2]
            mrp_formatted = f"₹{r[3]:,.2f}"
            description_text = r[4]
            page_number = r[5]
            catalog_file = r[6]
            
            # Log to Google Sheet with Category
            log_to_google_sheet(brand_name, cat_name, sku_code, mrp_formatted, description_text, "Camera Photo OCR")
            
            return {
                "status": "success",
                "detected_sku": clean_candidate,
                "products": [{
                    "brand": brand_name,
                    "category": cat_name,
                    "sku_cat_no": sku_code,
                    "mrp_inr": mrp_formatted,
                    "description": description_text,
                    "page_no": page_number,
                    "source_catalog": catalog_file
                }]
            }
            
    raise HTTPException(status_code=404, detail="No matching SKU detected in photo.")
