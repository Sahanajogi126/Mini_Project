"""
extract_text.py - PDF and Text Extraction Module
Extracts text from PDF files or processes plain text input.
"""
import pdfplumber
import os
import re


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as a string
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")
    
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    # Remove headers/footers or page numbers
                    page_text = re.sub(r'Page\s*\d+', '', page_text)
                    text += page_text + " "
                    print(f"✅ Extracted page {i+1}/{len(pdf.pages)}")
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    return text.strip()


def extract_text_from_file(file_path: str) -> str:
    """
    Extract text from a plain text file.
    
    Args:
        file_path: Path to the text file
        
    Returns:
        Text content as a string
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Text file not found: {file_path}")
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return text.strip()
    except Exception as e:
        raise Exception(f"Error reading text file: {str(e)}")


def get_text_from_input(pdf_path: str = None, text_path: str = None) -> str:
    """
    Get text from either PDF or text file.
    Prioritizes PDF if both are provided.
    
    Args:
        pdf_path: Optional path to PDF file
        text_path: Optional path to text file
        
    Returns:
        Extracted text as a string
    """
    if pdf_path and os.path.exists(pdf_path):
        return extract_text_from_pdf(pdf_path)
    elif text_path and os.path.exists(text_path):
        return extract_text_from_file(text_path)
    else:
        raise ValueError("No valid input file found. Provide either pdf_path or text_path.")


if __name__ == "__main__":
    # Test extraction
    uploads_dir = "uploads"
    pdf_path = os.path.join(uploads_dir, "sample.pdf")
    text_path = os.path.join(uploads_dir, "pasted_text.txt")
    
    try:
        text = get_text_from_input(pdf_path=pdf_path, text_path=text_path)
        print(f"\n✅ Extracted {len(text)} characters of text")
        print(f"Preview: {text[:200]}...")
    except Exception as e:
        print(f"❌ Error: {e}")

