# Documentation

This directory contains the Sphinx documentation for EntropPy.

## Building the Documentation

### Prerequisites

Install the required dependencies:

```bash
pip install -r requirements-dev.txt
```

### Build Commands

**HTML documentation (recommended):**

```bash
cd docs
make html
# or on Windows:
make.bat html
```

The built documentation will be in `docs/_build/html/`. Open `index.html` in your browser.

**Other formats:**

```bash
make latexpdf    # PDF via LaTeX
make epub        # EPUB ebook
make man         # Manual pages
```

## Documentation Structure

- `conf.py` - Sphinx configuration
- `index.rst` - Main documentation entry point
- `algorithms.rst` - Includes ALGORITHMS.md
- `efficiency.rst` - Includes EFFICIENCY.md
- `api/` - Auto-generated API reference from docstrings

## Adding Documentation

1. **Markdown files** (like `ALGORITHMS.md`) can be included directly using MyST parser
2. **API documentation** is auto-generated from docstrings using `sphinx.ext.autodoc`
3. **New pages** should be added to `index.rst` in the `toctree` directive

## Viewing Locally

After building with `make html`, you can view the documentation by opening:
```
docs/_build/html/index.html
```

Or use Python's HTTP server:

```bash
cd docs/_build/html
python -m http.server 8000
# Then visit http://localhost:8000
```
