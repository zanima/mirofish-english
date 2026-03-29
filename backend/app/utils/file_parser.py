"""
File parsing tool
Supports text extraction from PDF, Markdown, TXT files
"""

import os
from pathlib import Path
from typing import List, Optional


def _read_text_with_fallback(file_path: str) -> str:
    """
    Read text files, automatically detect encoding if UTF-8 fails.
    
    Use multi-level fallback strategy:
    1. First try UTF-8 decoding
    2. Use charset_normalizer to detect encoding
    3. Fallback to chardet to detect encoding
    4. Finally use UTF-8 + errors='replace' as a fallback
    
    Args:
        file_path: file path
        
    Returns:
        decoded text content
    """
    data = Path(file_path).read_bytes()
    
    # First try UTF-8
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        pass
    
    # Try using charset_normalizer to detect encoding
    encoding = None
    try:
        from charset_normalizer import from_bytes
        best = from_bytes(data).best()
        if best and best.encoding:
            encoding = best.encoding
    except Exception:
        pass
    
    # Fallback to chardet
    if not encoding:
        try:
            import chardet
            result = chardet.detect(data)
            encoding = result.get('encoding') if result else None
        except Exception:
            pass
    
    # Finally fallback: use UTF-8 + replace
    if not encoding:
        encoding = 'utf-8'
    
    return data.decode(encoding, errors='replace')


class FileParser:
    """File parser"""
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.md', '.markdown', '.txt', '.csv'}
    
    @classmethod
    def extract_text(cls, file_path: str) -> str:
        """
        Extract text from file
        
        Args:
            file_path: file path
            
        Returns:
            extracted text content
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        suffix = path.suffix.lower()
        
        if suffix not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file format: {suffix}")
        
        if suffix == '.pdf':
            return cls._extract_from_pdf(file_path)
        elif suffix in {'.md', '.markdown'}:
            return cls._extract_from_md(file_path)
        elif suffix == '.txt':
            return cls._extract_from_txt(file_path)
        elif suffix == '.csv':
            return cls._extract_from_csv(file_path)
        
        raise ValueError(f"Cannot handle file format: {suffix}")
    
    @staticmethod
    def _extract_from_pdf(file_path: str) -> str:
        """Extract text from PDF"""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise ImportError("PyMuPDF is required: pip install PyMuPDF")
        
        text_parts = []
        with fitz.open(file_path) as doc:
            for page in doc:
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
        
        return "\n\n".join(text_parts)
    
    @staticmethod
    def _extract_from_md(file_path: str) -> str:
        """Extract text from Markdown, support automatic encoding detection"""
        return _read_text_with_fallback(file_path)
    
    @staticmethod
    def _extract_from_txt(file_path: str) -> str:
        """Extract text from TXT, support automatic encoding detection"""
        return _read_text_with_fallback(file_path)

    @staticmethod
    def _extract_from_csv(file_path: str) -> str:
        """
        Extract text from CSV.
        Renders the CSV as a markdown table (column headers + rows) so the
        LLM can reason about the tabular data.
        """
        import csv
        import io

        raw_text = _read_text_with_fallback(file_path)
        reader = csv.reader(io.StringIO(raw_text))
        rows = list(reader)

        if not rows:
            return raw_text  # fallback: return raw text

        headers = rows[0]
        data_rows = rows[1:]

        # Build markdown table
        lines = []
        lines.append('| ' + ' | '.join(headers) + ' |')
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for row in data_rows[:500]:  # limit to first 500 rows
            # Pad row to match header count
            padded = row + [''] * (len(headers) - len(row))
            lines.append('| ' + ' | '.join(padded[:len(headers)]) + ' |')

        if len(data_rows) > 500:
            lines.append(f'\n... ({len(data_rows) - 500} more rows truncated)')

        return '\n'.join(lines)
    
    @classmethod
    def extract_from_multiple(cls, file_paths: List[str]) -> str:
        """
        Extract text from multiple files and merge
        
        Args:
            file_paths: list of file paths
            
        Returns:
            merged text
        """
        all_texts = []
        
        for i, file_path in enumerate(file_paths, 1):
            try:
                text = cls.extract_text(file_path)
                filename = Path(file_path).name
                all_texts.append(f"=== Document {i}: {filename} ===\\n{text}")
            except Exception as e:
                all_texts.append(f"=== Document {i}: {file_path} (Extraction failed: {str(e)}) ===")
        
        return "\n\n".join(all_texts)


def split_text_into_chunks(
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[str]:
    """
    Split the text into small chunks
    
    Args:
        text: Original text
        chunk_size: Number of characters per chunk
        overlap: Number of overlapping characters
        
    Returns:
        Text chunk list
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to split at sentence boundaries
        if end < len(text):
            # Find the nearest sentence terminator
            for sep in ['。', '！', '？', '.\n', '!\n', '?\n', '\n\n', '. ', '! ', '? ']:
                last_sep = text[start:end].rfind(sep)
                if last_sep != -1 and last_sep > chunk_size * 0.3:
                    end = start + last_sep + len(sep)
                    break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # The next chunk starts from the overlap position
        start = end - overlap if end < len(text) else len(text)
    
    return chunks

