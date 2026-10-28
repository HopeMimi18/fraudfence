"""Ephemeral, best-effort extraction of untrusted invoice fields.

Never persists originals or returns raw invoice text. Extracted fields are suggestions,
not identity/banking verification. External model providers receive none of this content.
"""
from __future__ import annotations
import io
import os
import shutil
from pathlib import Path
import re
from decimal import Decimal, InvalidOperation

MAX_BYTES = 4 * 1024 * 1024
MAX_PAGES = 3


def configure_local_tesseract(pytesseract):
    """Use the standard Windows install location if the executable is not on PATH."""
    if not shutil.which('tesseract'):
        candidate = Path(os.environ.get('TESSERACT_CMD', r'C:\Program Files\Tesseract-OCR\tesseract.exe'))
        if candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)



def extract_text(data: bytes, filename: str) -> tuple[str, str]:
    name = filename.lower().strip()
    if len(data) > MAX_BYTES:
        raise ValueError('Maximum invoice size is 4 MB')
    if name.endswith('.pdf'):
        if not data.startswith(b'%PDF-'):
            raise ValueError('This file is not a valid PDF')
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError('Encrypted PDFs are not supported')
            if not (1 <= len(reader.pages) <= MAX_PAGES):
                raise ValueError('Use an invoice PDF with 1-3 pages')
            txt = '\n'.join((page.extract_text() or '') for page in reader.pages)
        except ValueError:
            raise
        except Exception:
            raise ValueError('PDF text extraction failed; check the file') from None
        if txt.strip():
            return txt[:24000], 'PDF_TEXT'
        # Optional scanned-PDF OCR. Avoid dependence on external AI/OCR APIs.
        try:
            import fitz
            import pytesseract
            from PIL import Image
            configure_local_tesseract(pytesseract)
            result=[]
            pdf=fitz.open(stream=data,filetype='pdf')
            try:
                for page in pdf:
                    pix=page.get_pixmap(matrix=fitz.Matrix(1.4,1.4),colorspace=fitz.csRGB,alpha=False)
                    if pix.width * pix.height > 10_000_000:
                        raise ValueError('Scanned page is too large')
                    img=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                    result.append(pytesseract.image_to_string(img,config='--psm 6'))
            finally:
                pdf.close()
            return '\n'.join(result)[:24000], 'SCANNED_PDF_OCR'
        except ValueError:
            raise
        except Exception:
            raise ValueError('This is a scanned PDF. Install Tesseract OCR and optional PyMuPDF to read it') from None
    if name.endswith(('.png','.jpg','.jpeg')):
        if not (data.startswith(b'\x89PNG\r\n\x1a\n') or data[:3]==b'\xff\xd8\xff'):
            raise ValueError('File contents do not match PNG/JPEG format')
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
            import pytesseract
            configure_local_tesseract(pytesseract)
            with Image.open(io.BytesIO(data)) as img:
                if img.format not in ('PNG','JPEG'):
                    raise ValueError('Only PNG/JPEG invoice images are accepted')
                if img.width*img.height > 10_000_000:
                    raise ValueError('Image is too large; maximum 10 megapixels')
                img=ImageOps.exif_transpose(img).convert('RGB')
                return pytesseract.image_to_string(img,config='--psm 6')[:24000], 'IMAGE_OCR'
        except ValueError:
            raise
        except Exception:
            raise ValueError('Image OCR unavailable. Install Tesseract OCR to read invoice pictures') from None
    raise ValueError('Upload a PDF, PNG or JPEG invoice')


def parse_invoice(text: str, method: str='PDF_TEXT') -> dict:
    """Strict, explainable suggestions. Do not guess accounts from unlabeled numbers."""
    lines=[re.sub(r'\s+',' ',line).strip() for line in text.splitlines() if line.strip()]
    warnings=['Untrusted document: confirm extracted values against the invoice before checking.',
              'Supplier identity is chosen from an existing trusted record; document text cannot approve a supplier.']
    if method.endswith('OCR'):
        warnings.append('OCR can confuse digits and punctuation. Compare every digit with the original image.')
    result={'invoice_reference':None,'amount_zar':None,'bank_account':None,
            'registration':None,'legal_name':None,'extraction_method':method,
            'review_required':True,'warnings':warnings,'fields_found':[]}
    def assign(key,value):
        if value is not None:
            result[key]=value
            result['fields_found'].append(key)
    legal_names=[]
    # Only short, explicit supplier names or an unambiguous legal-name header.
    # These are DOCUMENT CLAIMS, not verified CIPC identities.
    for line in lines:
        m=re.match(r'(?i)^(?:supplier|vendor|seller|supplier legal name|registered legal name)\s*:\s*(.{3,130})$',line)
        if m:
            name=m.group(1).strip().strip(' .')
            if name and not re.search(r'(?i)\b(?:invoice|customer|account number)\b',name):
                legal_names.append(name)
    if not legal_names:
        headers=[]
        for line in lines[:9]:
            if re.match(r'(?i)^(?:bill to|ship to|customer|to:)\b',line):
                continue
            if (re.search(r'(?i)\b(?:\(pty\)\s*ltd|pty\s*ltd|proprietary\s*limited)\b',line)
                    and len(line)<=130 and not re.search(r'(?i)\b(?:invoice|demonstration|registered as)\b',line)):
                headers.append(line)
        if len(set(headers))==1:
            legal_names=headers
    refs=[]; accounts=[]; amounts=[]; registrations=[]
    for line in lines:
        # Only labeled values; never infer a bank account from arbitrary numeric content.
        m=re.search(r'(?i)\b(?:invoice\s*(?:no\.?|number|#|reference)|inv\s*(?:no\.?|#))\s*[:#-]?\s*([A-Za-z0-9][A-Za-z0-9/_-]{2,49})\b',line)
        if m: refs.append(m.group(1).rstrip('.'))
        m=re.search(r'(?i)\b(?:account\s*(?:number|no\.?|#)|bank\s*account\s*(?:number|no\.?|#)?)\s*[:#-]*\s*([0-9][0-9 -]{7,23})\b',line)
        if m:
            digits=re.sub(r'[ -]','',m.group(1))
            if 8<=len(digits)<=16: accounts.append(digits)
        m=re.search(r'(?i)\b(?:grand\s*total|total\s*(?:amount\s*)?due|amount\s*due|total\s*payable|invoice\s*total)\s*:?\s*(?:ZAR|R)\s*([0-9][0-9, ]*(?:\.[0-9]{2})?)',line)
        if m:
            try:
                value=Decimal(m.group(1).replace(',','').replace(' ',''))
                if value>0 and value<=Decimal('1000000000'):
                    amounts.append(str(value.quantize(Decimal('0.01'))))
            except InvalidOperation:
                pass
        m=re.search(r'(?i)\b(?:company\s*(?:reg(?:istration)?\.?|number)|registration\s*(?:no\.?|number))\s*:?\s*(\d{4}/\d{6}/\d{2})',line)
        if m: registrations.append(m.group(1))
    for key,items in [('invoice_reference',refs),('bank_account',accounts),('amount_zar',amounts),('registration',registrations),('legal_name',legal_names)]:
        values=list(dict.fromkeys(items))
        if len(values)==1:
            assign(key,values[0])
        elif len(values)>1:
            warnings.append(f'Multiple possible {key.replace("_"," ")} values detected; enter manually.')
        else:
            warnings.append(f'{key.replace("_"," ").title()} not found reliably; enter manually.')
    if result['legal_name'] is not None:
        warnings.append('Supplier name came from the UNTRUSTED invoice. Compare it with an independently verified supplier record.')
    return result
