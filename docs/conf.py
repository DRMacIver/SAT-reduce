"""Sphinx configuration."""
project = "SAT-reduce"
author = "David R. MacIver"
copyright = "2023, David R. MacIver"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx_click",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"
