import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.text.hyperlink import Hyperlink

import zipfile
import xml.etree.ElementTree as ET
import os
import re
import io
import html
import time
import json
import random
import string
from datetime import datetime
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse


def generate_onsite_code(length=6):
    """Generate a random alphanumeric code for onsite registration."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))


def generate_order_id():
    """
    Generate a unique order ID for payments.
    Format: {HHMMSS}{random} - 6 digit timestamp + random alphanumeric
    Matches the frontend generateOrderId() function.
    """
    now = datetime.now()
    timestamp = now.strftime('%H%M%S')
    # Generate 8 random alphanumeric characters (lowercase + digits, like JS toString(36))
    chars = string.ascii_lowercase + string.digits
    random_part = ''.join(random.choice(chars) for _ in range(8))
    return f"{timestamp}{random_part}"


def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Rate limiting decorator for API endpoints.
    Limits requests per IP address within a time window.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Get client IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0].strip()
            else:
                ip = request.META.get('REMOTE_ADDR', 'unknown')

            # Create cache key based on IP and endpoint
            cache_key = f"rate_limit:{func.__name__}:{ip}"

            # Get current request count and timestamp
            request_data = cache.get(cache_key)
            current_time = time.time()

            if request_data is None:
                # First request
                cache.set(cache_key, {'count': 1, 'start': current_time}, window_seconds)
            else:
                # Check if window has expired
                if current_time - request_data['start'] > window_seconds:
                    # Reset window
                    cache.set(cache_key, {'count': 1, 'start': current_time}, window_seconds)
                elif request_data['count'] >= max_requests:
                    # Rate limit exceeded
                    return JsonResponse(
                        {"code": "rate_limited", "message": "Too many requests. Please try again later."},
                        status=429,
                    )
                else:
                    # Increment counter
                    request_data['count'] += 1
                    remaining_time = window_seconds - (current_time - request_data['start'])
                    cache.set(cache_key, request_data, int(remaining_time) + 1)

            return func(request, *args, **kwargs)
        return wrapper
    return decorator


# File upload validation constants
ALLOWED_EXTENSIONS = {'.docx', '.odt'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Editor file upload validation constants
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'}
ALLOWED_ATTACHMENT_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.zip'}
MAX_EDITOR_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Image magic bytes
IMAGE_MAGIC_BYTES = {
    '.jpg': [b'\xff\xd8\xff'],
    '.jpeg': [b'\xff\xd8\xff'],
    '.png': [b'\x89PNG\r\n\x1a\n'],
    '.gif': [b'GIF87a', b'GIF89a'],
    '.webp': [b'RIFF'],  # WebP starts with RIFF
    '.svg': [b'<?xml', b'<svg'],  # SVG is XML-based
}


def validate_editor_file(file_name: str, file_content: bytes, file_type: str = 'image') -> tuple[bool, str]:
    """
    Validate editor file uploads (images and attachments) for security.
    Returns (is_valid, error_message).
    """
    # 1. Validate file size
    if len(file_content) > MAX_EDITOR_FILE_SIZE:
        return False, "File size exceeds maximum allowed (5MB)."

    if len(file_content) == 0:
        return False, "File is empty."

    # 2. Sanitize and validate filename
    safe_name = os.path.basename(file_name)
    if not safe_name or safe_name.startswith('.'):
        return False, "Invalid filename."

    # Validate extension based on file type
    _, ext = os.path.splitext(safe_name.lower())

    if file_type == 'image':
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return False, f"Invalid image type. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"

        # Validate magic bytes for images (except SVG which is text-based)
        if ext in IMAGE_MAGIC_BYTES:
            valid_magic = False
            for magic in IMAGE_MAGIC_BYTES[ext]:
                if file_content[:len(magic)] == magic:
                    valid_magic = True
                    break
            if not valid_magic and ext != '.svg':
                return False, "Invalid image file. File content does not match the declared type."
    else:
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            return False, f"Invalid file type. Allowed: {', '.join(ALLOWED_ATTACHMENT_EXTENSIONS)}"

    return True, ""


def validate_abstract_file(file_name: str, file_content: bytes) -> tuple[bool, str]:
    """
    Validate abstract file uploads for security.
    Returns (is_valid, error_message).
    """
    # 1. Validate file size
    if len(file_content) > MAX_FILE_SIZE:
        return False, "File size exceeds maximum allowed (10MB)."

    if len(file_content) == 0:
        return False, "File is empty."

    # 2. Sanitize and validate filename
    # Extract only the basename to prevent path traversal
    safe_name = os.path.basename(file_name)

    # Check for suspicious patterns
    if not safe_name or safe_name.startswith('.'):
        return False, "Invalid filename."

    # Validate extension
    _, ext = os.path.splitext(safe_name.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return False, "Invalid file type. Only DOCX and ODT files are allowed."

    # 3. Validate file magic bytes (both DOCX and ODT are ZIP-based)
    # ZIP magic bytes: PK (0x50 0x4B)
    if len(file_content) < 4 or file_content[:2] != b'PK':
        return False, "Invalid file format. File does not appear to be a valid DOCX or ODT."

    # 4. Verify it's actually a valid ZIP and contains expected content
    try:
        with zipfile.ZipFile(io.BytesIO(file_content), 'r') as zf:
            file_list = zf.namelist()

            if ext == '.docx':
                # DOCX must contain [Content_Types].xml and word/ directory
                if '[Content_Types].xml' not in file_list:
                    return False, "Invalid DOCX file structure."
                if not any(f.startswith('word/') for f in file_list):
                    return False, "Invalid DOCX file structure."

            elif ext == '.odt':
                # ODT must contain mimetype and content.xml
                if 'mimetype' not in file_list:
                    return False, "Invalid ODT file structure."
                if 'content.xml' not in file_list:
                    return False, "Invalid ODT file structure."
                # Verify mimetype content
                mimetype = zf.read('mimetype').decode('utf-8', errors='ignore').strip()
                if 'opendocument' not in mimetype.lower():
                    return False, "Invalid ODT mimetype."

    except zipfile.BadZipFile:
        return False, "Invalid file format. File is corrupted or not a valid document."
    except Exception:
        return False, "Could not validate file. Please ensure it is a valid DOCX or ODT file."

    return True, ""


def sanitize_email_header(value: str) -> str:
    """
    Sanitize email header values to prevent header injection attacks.
    Removes newlines and carriage returns that could be used to inject additional headers.
    """
    if not value:
        return ""
    # Remove any newlines, carriage returns, and null bytes that could be used for header injection
    return value.replace('\r', '').replace('\n', '').replace('\x00', '')


def validate_email_format(email: str) -> bool:
    """
    Basic email format validation.
    Returns True if the email appears to be valid format.
    """
    if not email or not isinstance(email, str):
        return False
    # Basic email regex - must have @ and at least one dot after @
    email_pattern = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    return bool(email_pattern.match(email.strip()))


def sanitize_filename(file_name: str) -> str:
    """Sanitize filename to prevent path traversal and other issues."""
    # Get basename only
    safe_name = os.path.basename(file_name)
    # Remove any characters that aren't alphanumeric, dash, underscore, or dot
    safe_name = re.sub(r'[^\w\-.]', '_', safe_name)
    # Prevent multiple dots (except for extension)
    parts = safe_name.rsplit('.', 1)
    if len(parts) == 2:
        parts[0] = parts[0].replace('.', '_')
        safe_name = '.'.join(parts)
    return safe_name

def __process_run(r, p):
    p_bold = p.style.font.bold
    p_italic = p.style.font.italic
    p_underline = p.style.font.underline
    p_subscript = p.style.font.subscript
    p_superscript = p.style.font.superscript
    
    if hasattr(r, 'font'):
        r_bold = r.font.bold if r.font.bold is not None else p_bold
        r_italic = r.font.italic if r.font.italic is not None else p_italic
        r_underline = r.font.underline if r.font.underline is not None else p_underline
        r_subscript = r.font.subscript if r.font.subscript is not None else p_subscript
        r_superscript = r.font.superscript if r.font.superscript is not None else p_superscript
    else:
        r_bold = p_bold
        r_italic = p_italic
        r_underline = p_underline
        r_subscript = p_subscript
        r_superscript = p_superscript
        
    # Escape HTML to prevent XSS attacks
    r_text = html.escape(r.text) if r.text else ''
    if r_bold:
        r_text = f'<b>{r_text}</b>'
    if r_italic:
        r_text = f'<i>{r_text}</i>'
    if r_underline:
        r_text = f'<u>{r_text}</u>'
    if r_subscript:
        r_text = f'<sub>{r_text}</sub>'
    if r_superscript:
        r_text = f'<sup>{r_text}</sup>'
    return r_text

def docx_to_html(file_path):
    """
    Convert a DOCX document to HTML focusing only on basic formatting:
    - Paragraph alignment
    - Bold, italic, underline
    - Superscript, subscript
    
    Args:
        file_path (str): Path to the DOCX file
        
    Returns:
        str: HTML content of the document
    """

    doc = docx.Document(file_path)
    html = ''
    for p in doc.paragraphs:
        p_alignment = 'left'
        if p.style.paragraph_format.alignment is not None:
            p_alignment = p.style.paragraph_format.alignment
        if p.alignment is not None:
            p_alignment = p.alignment
        if p_alignment == WD_ALIGN_PARAGRAPH.LEFT:
            p_alignment = 'left'
        elif p_alignment == WD_ALIGN_PARAGRAPH.CENTER:
            p_alignment = 'center'
        elif p_alignment == WD_ALIGN_PARAGRAPH.RIGHT:
            p_alignment = 'right'
        elif p_alignment == WD_ALIGN_PARAGRAPH.JUSTIFY:
            p_alignment = 'justify'
        html += f'<p class="docx_paragraphs" style="text-align: {p_alignment};">'
        for r_or_h in p.iter_inner_content():
            if isinstance(r_or_h, Hyperlink):
                for r in r_or_h.runs:
                    html += __process_run(r, p)
            else:
                html += __process_run(r_or_h, p)
        html += '</p>'
    return html

def __resolve_style(style_name, style_dict, style_hierarchy_dict, other_style_dict=None):
    """
    Recursively resolve a style by following the entire inheritance chain
    
    Args:
        style_name: The name of the style to resolve
        style_dict: Dictionary containing styles (either styles or automatic_styles)
        style_hierarchy_dict: Dictionary mapping style names to their parent style names
        other_style_dict: Optional secondary style dictionary to check (for cross-dictionary inheritance)
        
    Returns:
        dict: Fully resolved style properties
    """
    if style_name not in style_dict and (other_style_dict is None or style_name not in other_style_dict):
        return {}
        
    # Start with base style properties
    resolved_style = {}
    
    # First check if style exists in primary dictionary
    if style_name in style_dict:
        # Get parent style name if it exists
        parent_name = style_hierarchy_dict.get(style_name)
        
        if parent_name:
            # First check if parent is in the same dictionary
            if parent_name in style_dict:
                # Recursively resolve parent style first
                parent_style = __resolve_style(parent_name, style_dict, style_hierarchy_dict, other_style_dict)
                resolved_style.update(parent_style)
            # Then check if parent is in the other dictionary (if provided)
            elif other_style_dict and parent_name in other_style_dict:
                # For cross-dictionary inheritance (e.g., automatic style inheriting from document style)
                parent_style = __resolve_style(parent_name, other_style_dict, 
                                               {k: v for k, v in style_hierarchy_dict.items() if k in other_style_dict})
                resolved_style.update(parent_style)
        
        # Add this style's properties (overriding any inherited properties)
        resolved_style.update(style_dict[style_name])
        
    # If not in primary dictionary but in secondary, use that
    elif other_style_dict and style_name in other_style_dict:
        # For styles that only exist in the other dictionary
        resolved_style = __resolve_style(style_name, other_style_dict, 
                                         {k: v for k, v in style_hierarchy_dict.items() if k in other_style_dict})
        
    return resolved_style

def odt_to_html(file_path):
    """
    Convert an ODT document to HTML focusing only on basic formatting:
    - Paragraph alignment
    - Bold, italic, underline
    - Superscript, subscript
    
    Args:
        file_path (str): Path to the ODT file
        
    Returns:
        str: HTML content of the document
    """
    # ODT namespaces
    namespaces = {
        'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
        'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
        'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
        'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
    }
    
    # Dictionary to store styles (focus only on key formatting)
    styles = {}
    automatic_styles = {}
    
    # Open the ODT file as a zip archive
    with zipfile.ZipFile(file_path, 'r') as odt_file:
        # Extract and parse styles.xml
        if 'styles.xml' in odt_file.namelist():
            styles_content = odt_file.read('styles.xml')
            styles_root = ET.fromstring(styles_content)
            
            # Get style hierarchies (map of style name to parent style name)
            style_hierarchy = {}
            
            for style_elem in styles_root.findall('.//style:style', namespaces):
                style_name = style_elem.get('{{{0}}}name'.format(namespaces['style']))
                style_properties = {}
                
                # Get parent style name if it exists
                parent_style_name = style_elem.get('{{{0}}}parent-style-name'.format(namespaces['style']))
                if parent_style_name:
                    style_hierarchy[style_name] = parent_style_name
                
                # Paragraph properties (for alignment)
                para_prop = style_elem.find('.//style:paragraph-properties', namespaces)
                if para_prop is not None:
                    # Only extract alignment
                    fo_align = '{{{0}}}text-align'.format(namespaces['fo'])
                    if fo_align in para_prop.attrib:
                        style_properties[fo_align] = para_prop.attrib[fo_align]
                
                # Text properties (bold, italic, etc.)
                text_prop = style_elem.find('.//style:text-properties', namespaces)
                if text_prop is not None:
                    # Extract only bold, italic, underline, position (for sub/superscript)
                    fo_weight = '{{{0}}}font-weight'.format(namespaces['fo'])
                    fo_style = '{{{0}}}font-style'.format(namespaces['fo'])
                    style_underline = '{{{0}}}text-underline-style'.format(namespaces['style'])
                    style_position = '{{{0}}}text-position'.format(namespaces['style'])
                    
                    for attr_name in [fo_weight, fo_style, style_underline, style_position]:
                        if attr_name in text_prop.attrib:
                            style_properties[attr_name] = text_prop.attrib[attr_name]
                
                styles[style_name] = style_properties
        
        # Extract and parse content.xml
        content = odt_file.read('content.xml')
        root = ET.fromstring(content)
        
        # Get automatic style hierarchy
        auto_style_hierarchy = {}
        
        for auto_style in root.findall('.//office:automatic-styles/style:style', namespaces):
            style_name = auto_style.get('{{{0}}}name'.format(namespaces['style']))
            style_properties = {}
            
            # Get parent style name if it exists
            parent_style_name = auto_style.get('{{{0}}}parent-style-name'.format(namespaces['style']))
            if parent_style_name:
                auto_style_hierarchy[style_name] = parent_style_name
            
            # Paragraph properties (for alignment)
            para_prop = auto_style.find('.//style:paragraph-properties', namespaces)
            if para_prop is not None:
                # Only extract alignment
                fo_align = '{{{0}}}text-align'.format(namespaces['fo'])
                if fo_align in para_prop.attrib:
                    style_properties[fo_align] = para_prop.attrib[fo_align]
            
            # Text properties (bold, italic, etc.)
            text_prop = auto_style.find('.//style:text-properties', namespaces)
            if text_prop is not None:
                # Extract only bold, italic, underline, position (for sub/superscript)
                fo_weight = '{{{0}}}font-weight'.format(namespaces['fo'])
                fo_style = '{{{0}}}font-style'.format(namespaces['fo'])
                style_underline = '{{{0}}}text-underline-style'.format(namespaces['style'])
                style_position = '{{{0}}}text-position'.format(namespaces['style'])
                
                for attr_name in [fo_weight, fo_style, style_underline, style_position]:
                    if attr_name in text_prop.attrib:
                        style_properties[attr_name] = text_prop.attrib[attr_name]
            
            automatic_styles[style_name] = style_properties
        
        # Generate HTML
        html_output = []
        # Process paragraphs
        for paragraph in root.findall('.//text:p', namespaces):
            p_style_name = paragraph.get('{{{0}}}style-name'.format(namespaces['text']))
            
            # Get paragraph style name
            p_style_name = paragraph.get('{{{0}}}style-name'.format(namespaces['text']))
            
            # Get fully resolved paragraph style
            p_style = {}
            if p_style_name:
                # Combine both style hierarchies for complete resolution
                combined_hierarchy = {**style_hierarchy, **auto_style_hierarchy}
                
                # Try resolving from automatic styles first
                if p_style_name in automatic_styles:
                    p_style = __resolve_style(p_style_name, automatic_styles, combined_hierarchy, styles)
                # Then try document styles
                elif p_style_name in styles:
                    p_style = __resolve_style(p_style_name, styles, combined_hierarchy, automatic_styles)
            
            # Extract paragraph formatting attributes
            text_align = 'left'  # Default
            p_is_bold = False
            p_is_italic = False
            p_is_underline = False
            p_is_superscript = False
            p_is_subscript = False
            
            # Get alignment
            fo_align = '{{{0}}}text-align'.format(namespaces['fo'])
            if fo_align in p_style:
                text_align = p_style[fo_align]
                
            # Get basic text formatting from paragraph style (for inheritance)
            fo_weight = '{{{0}}}font-weight'.format(namespaces['fo'])
            if fo_weight in p_style and p_style[fo_weight] == 'bold':
                p_is_bold = True
                
            fo_style = '{{{0}}}font-style'.format(namespaces['fo'])
            if fo_style in p_style and p_style[fo_style] == 'italic':
                p_is_italic = True
                
            style_text_underline = '{{{0}}}text-underline-style'.format(namespaces['style'])
            if style_text_underline in p_style and p_style[style_text_underline] != 'none':
                p_is_underline = True
                
            style_text_position = '{{{0}}}text-position'.format(namespaces['style'])
            if style_text_position in p_style:
                position = p_style[style_text_position]
                if position.startswith('super'):
                    p_is_superscript = True
                elif position.startswith('sub'):
                    p_is_subscript = True
            
            # Start paragraph with alignment
            html_output.append(f'<p class="odt_paragraphs" style="text-align: {text_align};">')
            
            # Process paragraph content
            # First, handle direct text content of the paragraph with paragraph's formatting
            if paragraph.text and paragraph.text.strip():
                # Escape HTML to prevent XSS attacks
                text = html.escape(paragraph.text)

                # Apply paragraph formatting to direct text
                if p_is_subscript:
                    text = f'<sub>{text}</sub>'
                if p_is_superscript:
                    text = f'<sup>{text}</sup>'
                if p_is_underline:
                    text = f'<u>{text}</u>'
                if p_is_italic:
                    text = f'<i>{text}</i>'
                if p_is_bold:
                    text = f'<b>{text}</b>'

                html_output.append(text)
            
            # Process all children
            for child in paragraph:
                if child.tag == '{{{0}}}span'.format(namespaces['text']):
                    span_style_name = child.get('{{{0}}}style-name'.format(namespaces['text']))
                    span_style = {}
                    
                    # Get span style
                    if span_style_name in automatic_styles:
                        span_style = automatic_styles[span_style_name]
                    elif span_style_name in styles:
                        span_style = styles[span_style_name]
                    
                    # Process text with formatting - escape HTML to prevent XSS
                    text = html.escape(child.text) if child.text else ''

                    # Inherit formatting from paragraph style if not defined in span style
                    is_bold = p_is_bold
                    is_italic = p_is_italic
                    is_underline = p_is_underline
                    is_superscript = p_is_superscript
                    is_subscript = p_is_subscript
                    
                    # Override with span-specific formatting if defined
                    # Bold
                    fo_weight = '{{{0}}}font-weight'.format(namespaces['fo'])
                    if fo_weight in span_style:
                        is_bold = span_style[fo_weight] == 'bold'
                    
                    # Italic
                    fo_style = '{{{0}}}font-style'.format(namespaces['fo'])
                    if fo_style in span_style:
                        is_italic = span_style[fo_style] == 'italic'
                    
                    # Underline
                    style_text_underline = '{{{0}}}text-underline-style'.format(namespaces['style'])
                    if style_text_underline in span_style:
                        is_underline = span_style[style_text_underline] != 'none'
                    
                    # Superscript/subscript
                    style_text_position = '{{{0}}}text-position'.format(namespaces['style'])
                    if style_text_position in span_style:
                        position = span_style[style_text_position]
                        is_superscript = position.startswith('super')
                        is_subscript = position.startswith('sub')
                    
                    # Apply formatting (order matters for nested tags)
                    if is_subscript:
                        text = f'<sub>{text}</sub>'
                    if is_superscript:
                        text = f'<sup>{text}</sup>'
                    if is_underline:
                        text = f'<u>{text}</u>'
                    if is_italic:
                        text = f'<i>{text}</i>'
                    if is_bold:
                        text = f'<b>{text}</b>'

                    html_output.append(text)

                # Handle line breaks
                elif child.tag == '{{{0}}}line-break'.format(namespaces['text']):
                    html_output.append('<br/>')

                # Handle other elements (with paragraph formatting)
                elif child.text and child.text.strip():
                    # Escape HTML to prevent XSS
                    text = html.escape(child.text)

                    # Apply paragraph formatting
                    if p_is_subscript:
                        text = f'<sub>{text}</sub>'
                    if p_is_superscript:
                        text = f'<sup>{text}</sup>'
                    if p_is_underline:
                        text = f'<u>{text}</u>'
                    if p_is_italic:
                        text = f'<i>{text}</i>'
                    if p_is_bold:
                        text = f'<b>{text}</b>'

                    html_output.append(text)

                # Handle tail text (text between spans) with paragraph formatting
                if child.tail and child.tail.strip():
                    # Escape HTML to prevent XSS
                    text = html.escape(child.tail)

                    # Apply paragraph formatting
                    if p_is_subscript:
                        text = f'<sub>{text}</sub>'
                    if p_is_superscript:
                        text = f'<sup>{text}</sup>'
                    if p_is_underline:
                        text = f'<u>{text}</u>'
                    if p_is_italic:
                        text = f'<i>{text}</i>'
                    if p_is_bold:
                        text = f'<b>{text}</b>'

                    html_output.append(text)

            html_output.append('</p>')

    return ''.join(html_output)


def render_email_template(template_string, context_dict):
    """Render an email template as plain text.

    Emails are sent as text/plain, so Django's HTML autoescaping must be off:
    with it on, an event named "SCSOK & KSBMB" reaches the recipient as
    "SCSOK &amp; KSBMB", and any quote or angle bracket is mangled the same way.
    """
    from django.template import Context, Template

    return Template(template_string).render(Context(context_dict, autoescape=False))
