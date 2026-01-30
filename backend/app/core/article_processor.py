"""
Article/PDF Processor for BioDiscovery AI
v3.3 - Handles PDF article input for search

When user uploads a PDF article:
1. Extract text content
2. Identify title (first line or H1)
3. Identify abstract (between "Abstract" and "Introduction")
4. Concatenate with user query for enhanced search

Usage in workflow:
    from app.core.article_processor import process_article_input
    
    enhanced_text = process_article_input(
        user_query="HER2 binding",
        article_path="/path/to/article.pdf"
    )
    # Returns: "Title of Paper. Abstract text... HER2 binding"
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def extract_title_abstract_from_text(text: str) -> Tuple[str, str]:
    """
    Extract title and abstract from article text.
    
    Returns:
        (title, abstract) tuple
    """
    lines = text.split('\n')
    title = ""
    abstract = ""
    
    # Title is usually the first non-empty line
    for line in lines[:10]:
        line = line.strip()
        if line and len(line) > 10:
            title = line
            break
    
    # Find abstract section
    text_lower = text.lower()
    
    # Common abstract patterns
    abstract_patterns = [
        r'abstract\s*[\:\.]?\s*(.+?)(?=introduction|background|keywords|1\.|methods)',
        r'summary\s*[\:\.]?\s*(.+?)(?=introduction|background|keywords|1\.)',
    ]
    
    for pattern in abstract_patterns:
        match = re.search(pattern, text_lower, re.DOTALL | re.IGNORECASE)
        if match:
            # Get the actual text (not lowercased)
            start = match.start(1)
            end = match.end(1)
            abstract = text[start:end].strip()
            break
    
    # If no abstract found, use first paragraph after title
    if not abstract and len(lines) > 2:
        for i, line in enumerate(lines[2:15], start=2):
            if len(line.strip()) > 100:
                abstract = line.strip()
                break
    
    # Clean up
    title = re.sub(r'\s+', ' ', title).strip()[:500]
    abstract = re.sub(r'\s+', ' ', abstract).strip()[:2000]
    
    return title, abstract


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from PDF file.
    
    Uses PyMuPDF (fitz) if available, falls back to PyPDF2.
    """
    try:
        # Try PyMuPDF first (better quality)
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        text_parts = []
        
        for page_num in range(min(5, len(doc))):  # First 5 pages usually contain abstract
            page = doc[page_num]
            text_parts.append(page.get_text())
        
        doc.close()
        return '\n'.join(text_parts)
        
    except ImportError:
        logger.warning("PyMuPDF not available, trying PyPDF2")
        
        try:
            from PyPDF2 import PdfReader
            
            reader = PdfReader(pdf_path)
            text_parts = []
            
            for page_num in range(min(5, len(reader.pages))):
                page = reader.pages[page_num]
                text_parts.append(page.extract_text())
            
            return '\n'.join(text_parts)
            
        except ImportError:
            logger.error("No PDF library available. Install: pip install PyMuPDF or pip install PyPDF2")
            return ""


def extract_text_from_txt(txt_path: str) -> str:
    """Extract text from TXT file."""
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading TXT file: {e}")
        return ""


def process_article_input(
    user_query: str,
    article_path: Optional[str] = None,
    article_content: Optional[str] = None,
    max_context_length: int = 3000,
) -> str:
    """
    Process article input and combine with user query.
    
    Args:
        user_query: User's search query
        article_path: Path to PDF or TXT file
        article_content: Raw text content (if already extracted)
        max_context_length: Maximum length for article context
    
    Returns:
        Enhanced query string: "{title}. {abstract}. {user_query}"
    """
    if not article_path and not article_content:
        return user_query
    
    # Extract text from file if needed
    if article_path and not article_content:
        path = Path(article_path)
        
        if path.suffix.lower() == '.pdf':
            article_content = extract_text_from_pdf(article_path)
        elif path.suffix.lower() in ['.txt', '.md']:
            article_content = extract_text_from_txt(article_path)
        else:
            logger.warning(f"Unsupported file type: {path.suffix}")
            return user_query
    
    if not article_content:
        logger.warning("Could not extract article content")
        return user_query
    
    # Extract title and abstract
    title, abstract = extract_title_abstract_from_text(article_content)
    
    logger.info(f"📄 ARTICLE PROCESSED:")
    logger.info(f"   Title: {title[:100]}...")
    logger.info(f"   Abstract: {abstract[:200]}...")
    
    # Combine: Title + Abstract + User Query
    context_parts = []
    
    if title:
        context_parts.append(title)
    
    if abstract:
        # Truncate abstract if needed
        if len(abstract) > max_context_length:
            abstract = abstract[:max_context_length] + "..."
        context_parts.append(abstract)
    
    if user_query:
        context_parts.append(user_query)
    
    # Build enhanced query
    enhanced_query = ". ".join(context_parts)
    
    logger.info(f"   Enhanced query length: {len(enhanced_query)} chars")
    
    return enhanced_query


def get_article_metadata(
    article_path: Optional[str] = None,
    article_content: Optional[str] = None,
) -> dict:
    """
    Extract structured metadata from article.
    
    Returns:
        {
            "title": str,
            "abstract": str,
            "keywords": list[str],  # if found
            "doi": str,  # if found
        }
    """
    metadata = {
        "title": "",
        "abstract": "",
        "keywords": [],
        "doi": "",
    }
    
    if article_path and not article_content:
        path = Path(article_path)
        if path.suffix.lower() == '.pdf':
            article_content = extract_text_from_pdf(article_path)
        else:
            article_content = extract_text_from_txt(article_path)
    
    if not article_content:
        return metadata
    
    # Extract title and abstract
    title, abstract = extract_title_abstract_from_text(article_content)
    metadata["title"] = title
    metadata["abstract"] = abstract
    
    # Try to find DOI
    doi_pattern = r'10\.\d{4,}/[^\s]+'
    doi_match = re.search(doi_pattern, article_content)
    if doi_match:
        metadata["doi"] = doi_match.group()
    
    # Try to find keywords
    keywords_pattern = r'keywords?\s*[\:\.]?\s*([^\n]+)'
    keywords_match = re.search(keywords_pattern, article_content, re.IGNORECASE)
    if keywords_match:
        keywords_text = keywords_match.group(1)
        # Split by common delimiters
        keywords = re.split(r'[,;•]', keywords_text)
        metadata["keywords"] = [kw.strip() for kw in keywords if kw.strip()][:10]
    
    return metadata


# Example usage in workflow:
# 
# In node_encode or workflow.py:
# 
#     from app.core.article_processor import process_article_input
#     
#     # If article file provided, enhance the query
#     if article_path:
#         enhanced_text = process_article_input(
#             user_query=state.get("input_text", ""),
#             article_path=article_path
#         )
#         state["input_text"] = enhanced_text