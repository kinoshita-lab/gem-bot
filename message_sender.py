"""Discord message sending logic with code block splitting, table formatting, and LaTeX/table rendering."""

from __future__ import annotations

import io
import re
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from i18n import I18nManager
    from latex_renderer import LatexRenderer
    from table_renderer import TableRenderer


class MessageSenderMixin:
    """Mixin providing Discord message sending capabilities for GeminiBot.

    Expects the host class to have:
        - self.i18n: I18nManager
        - self.latex_renderer: LatexRenderer
        - self.table_renderer: TableRenderer
    """

    async def _send_text(self, channel: discord.abc.Messageable, text: str) -> None:
        """Send text to a channel, splitting intelligently.

        Ensures code blocks are sent as separate messages and not split mid-block
        if possible. Handles splitting of messages > 2000 chars.

        Args:
            channel: Discord channel to send to.
            text: Text to send.
        """
        text = text.strip()
        if not text:
            return

        # Split text by code blocks to treat them as independent parts
        # Regex captures the delimiter (code block) so we keep it in the list
        segments = re.split(r"(```[\s\S]*?```)", text)

        for segment in segments:
            if not segment.strip():
                continue

            if segment.startswith("```") and segment.endswith("```"):
                # -- CODE BLOCK --
                if len(segment) <= 2000:
                    await channel.send(segment)
                else:
                    # Handle massive code blocks > 2000 chars
                    await self._send_large_code_block(channel, segment)
            else:
                # -- REGULAR TEXT --
                if len(segment) <= 2000:
                    await channel.send(segment)
                else:
                    await self._send_large_text(channel, segment)

    async def _send_large_code_block(
        self, channel: discord.abc.Messageable, segment: str
    ) -> None:
        """Split and send a code block that exceeds 2000 characters.

        Args:
            channel: Discord channel to send to.
            segment: Code block string (with ``` wrappers).
        """
        content = segment[3:-3]  # Remove outer backticks

        # Extract language if present
        lang = ""
        first_newline = content.find("\n")
        if first_newline != -1:
            possible_lang = content[:first_newline].strip()
            if possible_lang.isalnum():  # Simple check for lang tag
                lang = possible_lang
                content = content[first_newline + 1 :]

        # Maximum content size per chunk (2000 - wrappers)
        # Wrapper overhead: ```lang\n...``` -> 3 + len(lang) + 1 + 3 = 7 + len(lang)
        wrapper_overhead = 7 + len(lang)
        chunk_size = 2000 - wrapper_overhead

        for i in range(0, len(content), chunk_size):
            chunk_content = content[i : i + chunk_size]
            chunk_msg = f"```{lang}\n{chunk_content}```"
            await channel.send(chunk_msg)

    async def _send_large_text(
        self, channel: discord.abc.Messageable, segment: str
    ) -> None:
        """Split and send regular text that exceeds 2000 characters.

        Args:
            channel: Discord channel to send to.
            segment: Text string to split and send.
        """
        current_chunk = ""
        lines = segment.split("\n")
        for line in lines:
            # +1 for the newline we'll add back
            if len(current_chunk) + len(line) + 1 > 2000:
                if current_chunk:
                    await channel.send(current_chunk)
                    current_chunk = ""

                # If a single line is massive, we still have to hard split it
                if len(line) > 2000:
                    for i in range(0, len(line), 2000):
                        await channel.send(line[i : i + 2000])
                else:
                    current_chunk = line
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line

        if current_chunk:
            await channel.send(current_chunk)

    def _format_tables(self, text: str) -> str:
        """Wrap Markdown tables in code blocks for better Discord display.

        Preserves existing code blocks to avoid double-wrapping.

        Args:
            text: Original markdown text.

        Returns:
            Text with tables wrapped in code blocks.
        """
        # 1. Identify existing code blocks to protect them
        code_block_ranges: list[tuple[int, int]] = []
        # Matches ```...``` (multi-line) or `...` (inline)
        for match in re.finditer(r"(`{1,3})[\s\S]*?\1", text):
            code_block_ranges.append(match.span())

        lines = text.split("\n")
        output_lines: list[str] = []
        in_table = False
        table_buffer: list[str] = []

        # Helper to check if a line is inside an existing code block
        def is_in_code_block(line_index: int, all_lines: list[str]) -> bool:
            current_pos = 0
            for i in range(line_index):
                current_pos += len(all_lines[i]) + 1  # +1 for newline

            line_end = current_pos + len(all_lines[line_index])

            for start, end in code_block_ranges:
                if (current_pos >= start and current_pos < end) or \
                   (line_end > start and line_end <= end) or \
                   (start >= current_pos and end <= line_end):
                    return True
            return False

        # Regex for table separator row (e.g., |---| or |:---:|)
        separator_pattern = re.compile(
            r"^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$"
        )

        for i, line in enumerate(lines):
            # If we are already building a table
            if in_table:
                # Check if this line continues the table (starts with |)
                if line.strip().startswith("|"):
                    table_buffer.append(line)
                else:
                    # End of table
                    output_lines.append("```")
                    output_lines.extend(table_buffer)
                    output_lines.append("```")
                    in_table = False
                    table_buffer = []
                    output_lines.append(line)
                continue

            # Check for table start (look ahead for separator)
            if not is_in_code_block(i, lines):
                # Potential header: current line has |, next line is separator
                if "|" in line and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if separator_pattern.match(next_line):
                        # Start of new table
                        in_table = True
                        table_buffer.append(line)
                        continue

            output_lines.append(line)

        # Flush any remaining table buffer
        if in_table:
            output_lines.append("```")
            output_lines.extend(table_buffer)
            output_lines.append("```")

        return "\n".join(output_lines)

    async def send_response(
        self, channel: discord.abc.Messageable, response_text: str
    ) -> None:
        """Send a response to a channel with inline LaTeX and table rendering.

        If the response contains LaTeX formulas ($$...$$) or Markdown tables,
        the text is split at those positions and rendered as images.

        Args:
            channel: Discord channel to send to.
            response_text: Response text, possibly containing LaTeX or tables.
        """
        # Handle empty response
        if not response_text:
            await channel.send("No response from Gemini.")
            return

        latex_renderer: LatexRenderer = self.latex_renderer  # type: ignore[attr-defined]
        table_renderer: TableRenderer = self.table_renderer  # type: ignore[attr-defined]
        i18n: I18nManager = self.i18n  # type: ignore[attr-defined]

        # Check for formulas or tables
        has_formulas = latex_renderer.enabled and latex_renderer.has_latex(response_text)
        has_tables = table_renderer.enabled and table_renderer.has_tables(response_text)

        # If neither, send as plain text with table formatting fallback
        if not has_formulas and not has_tables:
            await self._send_text(channel, response_text)
            return

        # Split text by tables first (tables contain priority)
        if has_tables:
            segments = table_renderer.split_text_by_tables(response_text)
        else:
            # No tables, just check for formulas
            segments = [{"type": "text", "content": response_text}]

        text_buffer = ""

        for segment in segments:
            if segment["type"] == "text":
                # Check for formulas in this text segment
                if latex_renderer.enabled and latex_renderer.has_latex(segment["content"]):
                    # Further split by formulas
                    formula_segments = latex_renderer.split_text_by_formulas(
                        segment["content"]
                    )

                    for formula_segment in formula_segments:
                        if formula_segment["type"] == "text":
                            text_buffer += formula_segment["content"]
                        else:
                            # Send accumulated text + formula
                            text_to_send = text_buffer + formula_segment["original"]
                            await self._send_text(channel, text_to_send)
                            text_buffer = ""

                            # Render and send formula as image
                            image_data = await latex_renderer.render_formula(
                                formula_segment["content"],
                                language=i18n.language,
                            )
                            if image_data:
                                try:
                                    file = discord.File(
                                        io.BytesIO(image_data),
                                        filename="formula.png",
                                    )
                                    await channel.send(file=file)
                                except Exception as e:
                                    print(f"Failed to send LaTeX image: {e}")
                else:
                    # No formulas, just accumulate text
                    text_buffer += segment["content"]

            else:  # table segment
                # Send accumulated text first
                if text_buffer.strip():
                    await self._send_text(channel, text_buffer)
                    text_buffer = ""

                # Try to render table as image
                table_data = segment["content"]
                image_data = await table_renderer.render_table(
                    table_data["headers"],
                    table_data["rows"],
                    table_data["alignments"],
                    language=i18n.language,
                )

                if image_data:
                    try:
                        file = discord.File(
                            io.BytesIO(image_data),
                            filename="table.png",
                        )
                        await channel.send(file=file)
                    except Exception as e:
                        print(f"Failed to send table image: {e}")
                else:
                    # Fallback to code block formatting
                    fallback_table = self._format_tables(segment["original"])
                    await self._send_text(channel, fallback_table)

        # Send any remaining text
        if text_buffer.strip():
            await self._send_text(channel, text_buffer)
