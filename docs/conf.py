"""Sphinx configuration file for EntropPy documentation."""

from datetime import datetime
import os
import sys

# Add the project root to the path so we can import entroppy
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Project information
project = "EntropPy"
copyright = f"{datetime.now().year}, Adam Goldsmith"
author = "Adam Goldsmith"

# Get version from the package
try:
    from entroppy import __version__

    release = __version__
    version = ".".join(__version__.split(".")[:2])  # Major.minor only
except ImportError:
    release = "0.7.0"
    version = "0.7"

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",  # For Google-style docstrings
    "myst_parser",  # For Markdown support
]

# Source file extensions
source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "restructuredtext",
    ".md": "markdown",
}

# Master document
master_doc = "index"

# HTML output options
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_theme_options = {
    "collapse_navigation": False,
    "display_version": True,
    "logo_only": False,
    "navigation_depth": 3,
    "style_external_links": True,
    "style_nav_header_background": "#2980B9",
}

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
    "special-members": "__init__",
}
autodoc_mock_imports = ["wordfreq", "english_words"]

# Napoleon settings (for Google-style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True

# MyST parser settings
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "dollarmath",
    "fieldlist",
    "html_admonition",
    "html_image",
    # "linkify",  # Requires linkify-it-py package
    "replacements",
    "smartquotes",
    "strikethrough",
    "substitution",
    "tasklist",
]

# Exclude patterns
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
