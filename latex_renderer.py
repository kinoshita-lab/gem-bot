"""LaTeX rendering utilities for Discord output.

Detects LaTeX formulas in text and renders them as PNG images
using local LaTeX installation (lualatex + Ghostscript).
"""

import asyncio
import re
import tempfile
from pathlib import Path


class LatexRenderer:
    """Renders LaTeX formulas to PNG images using local LaTeX installation.

    Uses LuaLaTeX and Ghostscript for rendering.
    """

    # LaTeX patterns - only display math (complex formulas)
    # Inline math ($...$) is excluded as it's usually simple and readable as text
    # Each tuple: (pattern, formula_type)
    LATEX_PATTERNS: list[tuple[str, str]] = [
        (r"\$\$(.+?)\$\$", "display"),  # $$...$$
        (r"\\\[(.+?)\\\]", "display"),  # \[...\]
    ]

    # Map language codes to Noto Sans CJK fonts
    FONT_MAP = {
        "ja": "Noto Sans CJK JP",
        "zh": "Noto Sans CJK SC",
        "zh-cn": "Noto Sans CJK SC",
        "zh-tw": "Noto Sans CJK TC",
        "ko": "Noto Sans CJK KR",
    }
    DEFAULT_FONT = "Noto Sans CJK JP"

    # LaTeX template for math formulas (white background, black text)
    LATEX_TEMPLATE = r"""\documentclass{standalone}
\usepackage{luatexja-fontspec}
\setmainjfont{FONT_NAME}
\setmainfont{FONT_NAME}
\usepackage{amsmath,amssymb}
\usepackage{xcolor}
\pagecolor{white}
\color{black}
\begin{document}
$\displaystyle FORMULA $
\end{document}
"""

    def __init__(self, enabled: bool = True):
        """Initialize the LaTeX renderer.

        Args:
            enabled: Whether LaTeX rendering is enabled.
        """
        self.enabled = enabled

    def extract_formulas(self, text: str) -> list[dict]:
        """Extract LaTeX formulas from text.

        Args:
            text: Text containing LaTeX formulas.

        Returns:
            List of dicts with 'latex', 'type' ('display' or 'inline'),
            'start', 'end', and 'original' keys.
        """
        if not self.enabled:
            return []

        formulas = []
        # Track matched positions to avoid overlapping matches
        matched_positions: set[int] = set()

        # First, identify code blocks to exclude their content from formula matching
        # Matches ```...``` (multi-line) or `...` (inline)
        code_block_pattern = r"(`{1,3})[\s\S]*?\1"
        code_block_ranges = []
        for match in re.finditer(code_block_pattern, text):
            code_block_ranges.append(match.span())

        for pattern, formula_type in self.LATEX_PATTERNS:
            for match in re.finditer(pattern, text, re.DOTALL):
                start, end = match.span()
                
                # Check if match is inside a code block
                in_code_block = False
                for cb_start, cb_end in code_block_ranges:
                    if start >= cb_start and end <= cb_end:
                        in_code_block = True
                        break
                
                if in_code_block:
                    continue

                # Skip if this position overlaps with already matched content
                if any(start <= pos < end for pos in matched_positions):
                    continue

                latex = match.group(1).strip()
                if latex:  # Only add non-empty formulas
                    formulas.append(
                        {
                            "latex": latex,
                            "type": formula_type,
                            "start": start,
                            "end": end,
                            "original": match.group(0),
                        }
                    )
                    matched_positions.update(range(start, end))

        # Sort by position in text
        formulas.sort(key=lambda x: x["start"])
        return formulas

    async def render_formula(
        self,
        latex: str,
        dpi: int = 300,
        language: str = "ja",
    ) -> bytes | None:
        """Render a LaTeX formula to PNG image using local LaTeX.

        Args:
            latex: LaTeX formula string (without delimiters).
            dpi: Resolution in dots per inch.
            language: Language code for font selection (e.g., "ja", "zh").

        Returns:
            PNG image data as bytes, or None if rendering failed.
        """
        if not self.enabled:
            return None

        # Determine font based on language
        font_name = self.FONT_MAP.get(language, self.DEFAULT_FONT)

        # Create temporary directory for LaTeX files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            tex_file = tmppath / "formula.tex"
            pdf_file = tmppath / "formula.pdf"
            png_file = tmppath / "formula.png"

            # Generate LaTeX source
            tex_content = self.LATEX_TEMPLATE.replace("FORMULA", latex)
            tex_content = tex_content.replace("FONT_NAME", font_name)

            # Write .tex file
            tex_file.write_text(tex_content, encoding="utf-8")

            try:
                # Run lualatex to generate .pdf directly
                lualatex_proc = await asyncio.create_subprocess_exec(
                    "lualatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory=" + str(tmppath),
                    str(tex_file),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    cwd=tmpdir,
                )
                await asyncio.wait_for(lualatex_proc.wait(), timeout=30.0)

                if lualatex_proc.returncode != 0 or not pdf_file.exists():
                    return None

                # Run gs (Ghostscript) to generate .png from .pdf
                gs_proc = await asyncio.create_subprocess_exec(
                    "gs",
                    "-dNOPAUSE",
                    "-dBATCH",
                    "-sDEVICE=png16m",
                    "-r" + str(dpi),
                    "-dGraphicsAlphaBits=4",
                    "-dTextAlphaBits=4",
                    "-sOutputFile=" + str(png_file),
                    str(pdf_file),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                    cwd=tmpdir,
                )
                await asyncio.wait_for(gs_proc.wait(), timeout=30.0)

                if gs_proc.returncode != 0 or not png_file.exists():
                    return None

                # Read and return PNG data
                return png_file.read_bytes()

            except asyncio.TimeoutError:
                return None
            except Exception:
                return None

    def has_latex(self, text: str) -> bool:
        """Check if text contains LaTeX formulas.

        Args:
            text: Text to check.

        Returns:
            True if LaTeX formulas are found.
        """
        return len(self.extract_formulas(text)) > 0

    def split_text_by_formulas(self, text: str) -> list[dict]:
        """Split text into segments by formula positions.

        Splits the text at each formula location, returning a list of
        segments that are either plain text or formulas.

        Args:
            text: Text containing LaTeX formulas.

        Returns:
            List of dicts with:
            - 'type': 'text' or 'formula'
            - 'content': Text content or LaTeX formula (without delimiters)
            - 'original': Original markup (for formula type only)

            Empty or whitespace-only text segments are excluded.
        """
        formulas = self.extract_formulas(text)

        # No formulas - return entire text as single segment
        if not formulas:
            stripped = text.strip()
            if stripped:
                return [{"type": "text", "content": text}]
            return []

        segments = []
        current_pos = 0

        for formula in formulas:
            # Add text segment before this formula (if non-empty)
            if current_pos < formula["start"]:
                text_segment = text[current_pos : formula["start"]]
                if text_segment.strip():
                    segments.append({"type": "text", "content": text_segment})

            # Add formula segment
            segments.append(
                {
                    "type": "formula",
                    "content": formula["latex"],
                    "original": formula["original"],
                }
            )

            current_pos = formula["end"]

        # Add remaining text after last formula (if non-empty)
        if current_pos < len(text):
            text_segment = text[current_pos:]
            if text_segment.strip():
                segments.append({"type": "text", "content": text_segment})

        return segments
