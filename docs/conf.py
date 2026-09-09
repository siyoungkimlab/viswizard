project = "viswizard"
copyright = "2026, Siyoung Kim"
author = "Siyoung Kim"
release = "0.1.0"  # kept in step with the test suite

extensions = []
templates_path = ["_templates"]
exclude_patterns = ["_build"]
html_static_path = ["_static"]
html_css_files = ["custom.css"]

html_theme = "furo"
# Dark in both modes: these pages are about how molecules look on a black
# background, and the color swatches are drawn for a dark ground.
_dark = {
    "color-background-primary": "#131316",
    "color-background-secondary": "#0e0e11",
    "color-foreground-primary": "#e4e4e7",
    "color-foreground-secondary": "#a1a1aa",
    "color-brand-primary": "#a6e6a6",
    "color-brand-content": "#a6e6a6",
    "color-background-hover": "#1c1c21",
    "color-api-background": "#1a1a1f",
    "color-highlight-on-target": "#26262c",
}
html_theme_options = {
    "light_css_variables": dict(_dark),
    "dark_css_variables": dict(_dark),
    "sidebar_hide_name": False,
}
