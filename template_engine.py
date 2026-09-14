"""
Template engine module.
Renders Jinja2 HTML email templates with client data from Google Sheets.
"""

import os
import logging
from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError

logger = logging.getLogger(__name__)

# Template directory path
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates", "email_templates")


def _get_env():
    """Create a Jinja2 environment configured for email templates.
    
    Returns:
        jinja2.Environment: Configured Jinja2 environment
    """
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_email(template_name, context):
    """Render an email template with the given context data.
    
    Any key in the context dictionary becomes a template variable.
    For example, if your Google Sheet has columns 'Name' and 'Company',
    you can use {{ Name }} and {{ Company }} in your template.
    
    Args:
        template_name: Name of the template file (e.g., 'default.html')
        context: Dictionary of template variables (typically a sheet row)
        
    Returns:
        str: Rendered HTML content
        
    Raises:
        TemplateNotFound: If the template file doesn't exist
        TemplateSyntaxError: If the template has syntax errors
    """
    env = _get_env()
    
    # Clean context — remove internal keys (those starting with '_')
    clean_context = {k: v for k, v in context.items() if not k.startswith("_")}
    
    try:
        template = env.get_template(template_name)
        rendered = template.render(**clean_context)
        logger.info(f"Rendered template '{template_name}' with {len(clean_context)} variables")
        return rendered
    except TemplateNotFound:
        logger.error(f"Template not found: {template_name}")
        raise
    except TemplateSyntaxError as e:
        logger.error(f"Template syntax error in {template_name}: {e}")
        raise


def render_subject(subject_template, context):
    """Render an email subject line with template variables.
    
    Subject lines can contain {{ variable }} placeholders just like the body.
    
    Args:
        subject_template: Subject string with optional Jinja2 placeholders
        context: Dictionary of template variables
        
    Returns:
        str: Rendered subject line
    """
    env = Environment(autoescape=False)
    clean_context = {k: v for k, v in context.items() if not k.startswith("_")}
    
    try:
        template = env.from_string(subject_template)
        return template.render(**clean_context)
    except Exception as e:
        logger.warning(f"Failed to render subject template, using raw: {e}")
        return subject_template


def list_templates():
    """List all available email templates.
    
    Returns:
        list[dict]: List of template info dicts with 'name' and 'path' keys
    """
    templates = []
    if os.path.exists(TEMPLATE_DIR):
        for filename in os.listdir(TEMPLATE_DIR):
            if filename.endswith((".html", ".htm")):
                templates.append({
                    "name": filename,
                    "path": os.path.join(TEMPLATE_DIR, filename),
                })
    return templates


def get_template_content(template_name):
    """Read the raw content of a template file.
    
    Args:
        template_name: Name of the template file
        
    Returns:
        str: Raw template content, or empty string if not found
    """
    template_path = os.path.join(TEMPLATE_DIR, template_name)
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def preview_template(template_name, sample_data=None):
    """Render a template with sample data for preview.
    
    Args:
        template_name: Name of the template file
        sample_data: Optional sample data dict. If None, uses defaults.
        
    Returns:
        str: Rendered HTML preview
    """
    if sample_data is None:
        sample_data = {
            "Name": "John Doe",
            "Email": "john@example.com",
            "Company": "Acme Corp",
            "Position": "CEO",
            "Custom_Message": "We'd love to connect with you!",
        }
    
    return render_email(template_name, sample_data)
