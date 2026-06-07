from app.src.core_etl import extract_and_clean_html

def test_extract_and_clean_html(url=None):
    if url is None:
        url = "https://retinia.mx/agudeza-visual-av/"
    text = extract_and_clean_html(url)
    assert isinstance(text, str), "La función debe retornar un string."
    print(f"Extracted text length: {len(text)} characters")
    print(f"Extracted text sample: {text[:200]}...")
    return text

if __name__ == "__main__":
    test_extract_and_clean_html()
