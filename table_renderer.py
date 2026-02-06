"""Markdown table rendering to PNG images using LaTeX."""

import asyncio
import re
import tempfile
from pathlib import Path


class TableRenderer:
    """Renders Markdown tables to PNG images using local LaTeX installation.

    Uses pLaTeX, dvipdfmx, and Ghostscript for rendering.
    """

    # Regex for detecting table separator row (e.g., |---| or |:---:|)
    # Matches tables with or without closing pipes, and handles alignment markers
    # Supports formats: |---|---|, |:---|:---:|, :---|:---:, etc.
    SEPARATOR_PATTERN = re.compile(
        r"^\s*\|?"
        r"(?:\s*:?-+:?\s*\|)+"
        r"(?:\s*:?-+:?\s*)?"
        r"\|?\s*$"
    )

    # Map language codes to Noto Sans CJK fonts
    FONT_MAP = {
        "ja": "Noto Sans CJK JP",
        "zh": "Noto Sans CJK SC",
        "zh-cn": "Noto Sans CJK SC",
        "zh-tw": "Noto Sans CJK TC",
        "ko": "Noto Sans CJK KR",
    }
    DEFAULT_FONT = "Noto Sans CJK JP"

    # LaTeX template with Japanese support and booktabs for nicer tables
    LATEX_TEMPLATE = r"""\documentclass{standalone}
\usepackage{luatexja-fontspec}
\setmainjfont{FONT_NAME}
\setmainfont{FONT_NAME}
\usepackage{booktabs}
\usepackage{xcolor}
\pagecolor{white}
\color{black}
\pagestyle{empty}
\setlength{\tabcolsep}{8pt}
\begin{document}
\begin{tabular}{COLUMN_SPEC}
TABLE_BODY
\end{tabular}
\end{document}
"""

    def __init__(self, enabled: bool = True):
        """Initialize the table renderer.

        Args:
            enabled: Whether table rendering is enabled.
        """
        self.enabled = enabled

    def extract_tables(self, text: str) -> list[dict]:
        """Extract Markdown tables from text.

        Args:
            text: Text containing Markdown tables.

        Returns:
            List of dicts with 'headers', 'rows', 'start', 'end', 'original' keys.
        """
        if not self.enabled:
            return []

        tables = []
        code_block_ranges = self._find_code_blocks(text)
        lines = text.split("\n")
        i = 0

        while i < len(lines):
            # Skip if inside code block
            if self._line_in_code_block(i, lines, code_block_ranges):
                i += 1
                continue

            # Check for potential table start
            if "|" in lines[i] and i + 1 < len(lines):
                # Check if next line is separator
                if self.SEPARATOR_PATTERN.match(lines[i + 1]):
                    # Parse table
                    table = self._parse_table(lines, i)
                    if table:
                        tables.append(table)
                        i = table["end_line"] + 1
                        continue

            i += 1

        return tables

    def _find_code_blocks(self, text: str) -> list[tuple[int, int]]:
        """Find code block ranges to exclude from table detection.

        Args:
            text: Text to search.

        Returns:
            List of (start, end) tuples.
        """
        code_block_ranges = []
        for match in re.finditer(r"(`{1,3})[\s\S]*?\1", text):
            code_block_ranges.append(match.span())
        return code_block_ranges

    def _line_in_code_block(
        self, line_index: int, lines: list[str], code_block_ranges: list[tuple[int, int]]
    ) -> bool:
        """Check if a line is inside a code block.

        Args:
            line_index: Index of the line to check.
            lines: List of all lines.
            code_block_ranges: List of code block ranges.

        Returns:
            True if line is inside a code block.
        """
        current_pos = 0
        for i in range(line_index):
            current_pos += len(lines[i]) + 1

        line_end = current_pos + len(lines[line_index])

        for start, end in code_block_ranges:
            if (current_pos >= start and current_pos < end) or \
               (line_end > start and line_end <= end) or \
               (start >= current_pos and end <= line_end):
                return True
        return False

    def _parse_table(self, lines: list[str], start_line: int) -> dict | None:
        """Parse a table starting from header line.

        Args:
            lines: List of all text lines.
            start_line: Index of the header line.

        Returns:
            Table dict with 'headers', 'rows', 'start_line', 'end_line', 'original'
            or None if parsing fails.
        """
        table_lines = []
        i = start_line

        # Collect table lines (all lines starting with |)
        while i < len(lines) and lines[i].strip().startswith("|"):
            table_lines.append(lines[i])
            i += 1

        if len(table_lines) < 2:
            return None  # Need at least header and separator

        # Parse header (first line)
        headers = self._parse_row(table_lines[0])

        # Skip separator line (index 1)
        # Parse data rows (index 2 onwards)
        rows = []
        for line in table_lines[2:]:
            row = self._parse_row(line)
            if row:  # Skip empty rows
                rows.append(row)

        if not rows:
            return None

        # Calculate positions in original text
        start_pos = sum(len(line) + 1 for line in lines[:start_line])
        end_line = start_line + len(table_lines) - 1
        end_pos = sum(len(line) + 1 for line in lines[:end_line + 1])

        original = "\n".join(table_lines)

        # Parse separator line (index 1) to get column alignments
        separator_line = table_lines[1] if len(table_lines) > 1 else ""
        alignments = self._parse_alignment(separator_line, len(headers))

        return {
            "headers": headers,
            "rows": rows,
            "alignments": alignments,
            "start_line": start_line,
            "end_line": end_line,
            "start": start_pos,
            "end": end_pos,
            "original": original,
        }

    def _parse_alignment(self, separator_line: str, num_cols: int) -> list[str]:
        """Parse column alignment from Markdown separator row.

        Args:
            separator_line: Markdown separator row (e.g., "|:---|---:|").
            num_cols: Number of columns in the table.

        Returns:
            List of alignment characters ('l' for left, 'c' for center, 'r' for right).
            Default is 'l' (left-aligned) if not specified.
        """
        alignments = []

        if not separator_line:
            return ["l"] * num_cols

        cells = separator_line.strip().strip("|").split("|")

        for cell in cells:
            cell = cell.strip()
            if not cell:
                continue

            if cell.startswith(":") and cell.endswith(":"):
                alignments.append("c")
            elif cell.startswith(":"):
                alignments.append("l")
            elif cell.endswith(":"):
                alignments.append("r")
            else:
                alignments.append("l")

        while len(alignments) < num_cols:
            alignments.append("l")

        return alignments

    def _parse_row(self, line: str) -> list[str]:
        """Parse a table row, splitting by | and stripping whitespace.

        Args:
            line: Table row line.

        Returns:
            List of cell values.
        """
        # Remove leading/trailing pipes and split by |
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        return cells

    async def render_table(
        self,
        headers: list[str],
        rows: list[list[str]],
        alignments: list[str] | None = None,
        dpi: int = 300,
        language: str = "ja",
    ) -> bytes | None:
        """Render a table to PNG image using LaTeX.

        Args:
            headers: List of header cell values.
            rows: List of rows, each a list of cell values.
            alignments: List of alignment characters ('l', 'c', 'r') for each column.
                        Default is left-aligned for all columns.
            dpi: Resolution in dots per inch.
            language: Language code for font selection (e.g., "ja", "zh").

        Returns:
            PNG image data as bytes, or None if rendering failed.
        """
        if not self.enabled or not headers or not rows:
            return None

        # Determine font based on language
        font_name = self.FONT_MAP.get(language, self.DEFAULT_FONT)

        # Determine column spec with alignments (default left-aligned)
        num_cols = len(headers)
        if alignments is None:
            alignments = ["l"] * num_cols

        col_spec = "|" + "|".join(alignments) + "|"

        # Build LaTeX table body
        table_body = []

        # Header row
        table_body.append("\\hline")
        table_body.append(
            " & ".join(
                self._escape_latex(self._strip_markdown(cell))
                for cell in headers
            ) + " \\\\"
        )

        # Data rows
        table_body.append("\\hline")
        for row in rows:
            # Pad row to match number of columns
            padded_row = row + [""] * (num_cols - len(row))
            table_body.append(
                " & ".join(
                    self._escape_latex(self._strip_markdown(cell))
                    for cell in padded_row
                ) + " \\\\"
            )
        table_body.append("\\hline")

        # Generate LaTeX source
        tex_content = self.LATEX_TEMPLATE.replace("COLUMN_SPEC", col_spec)
        tex_content = tex_content.replace("TABLE_BODY", "\n".join(table_body))
        tex_content = tex_content.replace("FONT_NAME", font_name)

        # Create temporary directory and render
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            tex_file = tmppath / "table.tex"
            pdf_file = tmppath / "table.pdf"
            png_file = tmppath / "table.png"

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

                return png_file.read_bytes()

            except asyncio.TimeoutError:
                return None
            except Exception:
                return None

    def _strip_markdown(self, text: str) -> str:
        """Remove Markdown syntax from text.

        Args:
            text: Text containing Markdown syntax.

        Returns:
            Text with Markdown syntax removed.
        """
        # Bold: **text** or __text__ → text
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)

        # Italic: *text* or _text_ → text
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # Code: `text` → text
        text = re.sub(r'`(.+?)`', r'\1', text)

        return text

    def _escape_latex(self, text: str) -> str:
        """Escape special LaTeX characters.

        Args:
            text: Text to escape.

        Returns:
            Escaped text.
        """
        # First, protect \\ (LaTeX newline) with a temporary placeholder
        temp_placeholder = "\x00TEMP_NEWLINE\x00"
        escaped = text.replace("\\\\", temp_placeholder)

        # Escape other special characters
        replacements = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }

        for char, replacement in replacements.items():
            escaped = escaped.replace(char, replacement)

        # Restore \\ (LaTeX newline)
        escaped = escaped.replace(temp_placeholder, r"\\")

        return escaped

    def has_tables(self, text: str) -> bool:
        """Check if text contains Markdown tables.

        Args:
            text: Text to check.

        Returns:
            True if tables are found.
        """
        return len(self.extract_tables(text)) > 0

    def split_text_by_tables(self, text: str) -> list[dict]:
        """Split text into segments by table positions.

        Args:
            text: Text containing Markdown tables.

        Returns:
            List of dicts with:
            - 'type': 'text' or 'table'
            - 'content': Text content or table dict (with headers, rows)
            - 'original': Original markup (for table type only)
        """
        tables = self.extract_tables(text)

        if not tables:
            stripped = text.strip()
            if stripped:
                return [{"type": "text", "content": text}]
            return []

        segments = []
        current_pos = 0

        for table in tables:
            # Add text segment before this table (if non-empty)
            if current_pos < table["start"]:
                text_segment = text[current_pos : table["start"]]
                if text_segment.strip():
                    segments.append({"type": "text", "content": text_segment})

            # Add table segment
            segments.append({
                "type": "table",
                "content": {
                    "headers": table["headers"],
                    "rows": table["rows"],
                    "alignments": table["alignments"],
                },
                "original": table["original"],
            })

            current_pos = table["end"]

        # Add remaining text after last table (if non-empty)
        if current_pos < len(text):
            text_segment = text[current_pos:]
            if text_segment.strip():
                segments.append({"type": "text", "content": text_segment})

        return segments
