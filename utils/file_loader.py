from PyPDF2 import PdfReader

def load_file(file):
    """
    Load a file from the local filesystem and return the text content.
    """
    if file.type == "application/pdf":
        pdf = PdfReader(file)
        text = "\n".join([(page.extract_text() or "") for page in pdf.pages])
    else:
        text = str(file.read(), "utf-8")
    return text
