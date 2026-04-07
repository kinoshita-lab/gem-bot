"""Gemini API interaction logic: ask_gemini, function call handling, and response processing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp
from google.genai import types

import asyncio

if TYPE_CHECKING:
    from google import genai

    from calendar_tools import CalendarToolHandler
    from history_manager import HistoryManager
    from i18n import I18nManager
    from tasks_tools import TasksToolHandler


class GeminiClientMixin:
    """Mixin providing Gemini API interaction for GeminiBot.

    Expects the host class to have:
        - self.gemini_client: genai.Client
        - self.conversation_history: dict[int, list]
        - self.history_manager: HistoryManager
        - self.i18n: I18nManager
        - self.calendar_tool_handler: CalendarToolHandler | None
        - self.tasks_tool_handler: TasksToolHandler | None
        - self.channel_tool_mode: dict[int, str]
        - self.get_model(channel_id) -> str
        - self.get_tool_mode(channel_id) -> str
        - self._save_history_to_disk(channel_id) -> None
        - self._format_usage_cost(usage_metadata, model) -> str  (from PricingMixin)
    """

    _RETRYABLE_ERROR_PATTERNS: frozenset[str] = frozenset({
        "DEADLINE_EXCEEDED", "504", "500", "503", "INTERNAL",
    })
    _MAX_API_RETRIES: int = 3
    _INITIAL_RETRY_DELAY: float = 2.0

    # =========================================================================
    # Thought Extraction
    # =========================================================================

    def _extract_thought_signature(self, response: Any) -> bytes | None:
        """Extract thought_signature from Gemini response.

        Args:
            response: Gemini API response.

        Returns:
            Thought signature as bytes, or None if not found.
        """
        if not response.candidates:
            return None

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            return None

        for part in candidate.content.parts:
            if hasattr(part, "thought_signature") and part.thought_signature:
                return part.thought_signature
        return None

    def _extract_thought_text(self, response: Any) -> str | None:
        """Extract thought process text from Gemini response.

        Args:
            response: Gemini API response.

        Returns:
            Thought process text, or None if not found.
        """
        if not response.candidates:
            return None

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            return None

        for part in candidate.content.parts:
            if hasattr(part, "thought") and part.thought:
                if hasattr(part, "text") and part.text:
                    return part.text
        return None

    # =========================================================================
    # ask_gemini Helper Methods
    # =========================================================================

    def _build_user_content(
        self,
        prompt: str,
        images: list[tuple[bytes, str]] | None = None,
    ) -> types.Content:
        """Build user content from prompt and optional images.

        Args:
            prompt: Text prompt from user.
            images: Optional list of (image_data, mime_type) tuples.

        Returns:
            Content object for the user message.
        """
        parts: list[types.Part] = []

        # Add images first if provided
        if images:
            for image_data, mime_type in images:
                parts.append(
                    types.Part.from_bytes(data=image_data, mime_type=mime_type)
                )

        # Add text prompt
        parts.append(types.Part.from_text(text=prompt))

        return types.Content(role="user", parts=parts)

    def _get_tools_for_mode(self, channel_id: int) -> list:
        """Get the appropriate tools based on channel's tool mode.

        Args:
            channel_id: Discord channel ID.

        Returns:
            List of Tool objects for the current mode.
        """
        from calendar_tools import get_calendar_tools
        from tasks_tools import get_tasks_tools

        i18n: I18nManager = self.i18n  # type: ignore[attr-defined]
        tool_mode = self.get_tool_mode(channel_id)  # type: ignore[attr-defined]

        if tool_mode == "calendar" and self.calendar_tool_handler:  # type: ignore[attr-defined]
            return get_calendar_tools(i18n)
        elif tool_mode == "todo" and self.tasks_tool_handler:  # type: ignore[attr-defined]
            return get_tasks_tools(i18n)
        else:
            # Default: Google Search
            return [types.Tool(google_search=types.GoogleSearch())]

    # Mode-specific system prompt instruction keys (mapped to i18n keys)
    _MODE_INSTRUCTION_KEYS: dict[str, str] = {
        "default": "mode_instruction_default",
        "todo": "mode_instruction_todo",
        "calendar": "mode_instruction_calendar",
    }

    def _get_mode_instruction(self, mode: str) -> str:
        """Get localized mode instruction for the given tool mode.

        Args:
            mode: Tool mode name ("todo", "calendar", etc.)

        Returns:
            Localized mode instruction string, or empty string if not applicable.
        """
        i18n_key = self._MODE_INSTRUCTION_KEYS.get(mode)
        if i18n_key:
            return self.i18n.t(i18n_key)  # type: ignore[attr-defined]
        return ""

    def _build_system_prompt(self, channel_id: int) -> str:
        """Build the system prompt with mode-specific instructions.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Complete system prompt string.
        """
        history_manager: HistoryManager = self.history_manager  # type: ignore[attr-defined]
        base_prompt = history_manager.load_system_prompt(channel_id)
        tool_mode = self.get_tool_mode(channel_id)  # type: ignore[attr-defined]

        # Add mode-specific instruction if applicable
        mode_instruction = self._get_mode_instruction(tool_mode)
        if mode_instruction:
            if base_prompt:
                # Structure with XML tags to clarify priority
                return f"""<priority-instructions>
{mode_instruction}
</priority-instructions>

<base-instructions>
{base_prompt}
</base-instructions>"""
            return mode_instruction

        return base_prompt

    async def _extract_grounding_sources(self, response: Any) -> list[dict]:
        """Extract source URLs and titles from grounding metadata.

        Args:
            response: Gemini API response.

        Returns:
            List of source dictionaries with 'uri' and 'title' keys.
        """
        sources: list[dict] = []

        # Early return if no candidates
        if not response.candidates:
            return sources

        candidate = response.candidates[0]

        # Check for grounding_metadata
        if not hasattr(candidate, "grounding_metadata") or not candidate.grounding_metadata:
            return sources

        grounding_metadata = candidate.grounding_metadata

        # Extract from grounding_chunks (contains web sources)
        if hasattr(grounding_metadata, "grounding_chunks") and grounding_metadata.grounding_chunks:
            for chunk in grounding_metadata.grounding_chunks:
                if hasattr(chunk, "web") and chunk.web:
                    web = chunk.web
                    source: dict[str, str] = {}
                    if hasattr(web, "uri") and web.uri:
                        source["uri"] = web.uri
                    if hasattr(web, "title") and web.title:
                        source["title"] = web.title
                    if source.get("uri"):
                        sources.append(source)

        # Deduplicate by URI while preserving order
        seen_uris: set[str] = set()
        unique_sources: list[dict] = []
        for source in sources:
            uri = source.get("uri")
            if uri and uri not in seen_uris:
                seen_uris.add(uri)
                unique_sources.append(source)

        # Resolve vertexaisearch URLs
        async with aiohttp.ClientSession() as session:
            for source in unique_sources:
                uri = source.get("uri")
                if uri and "vertexaisearch.cloud.google.com" in uri:
                    try:
                        async with session.head(
                            uri,
                            allow_redirects=True,
                            timeout=aiohttp.ClientTimeout(total=5),
                        ) as resp:
                            source["uri"] = str(resp.url)
                    except Exception:
                        # Fallback to original URI if resolution fails
                        pass

        return unique_sources

    def _format_grounding_sources(self, sources: list[dict]) -> str:
        """Format grounding sources as a reference section.

        Args:
            sources: List of source dictionaries with 'uri' and 'title' keys.

        Returns:
            Formatted reference section string, or empty string if no sources.
        """
        if not sources:
            return ""

        i18n: I18nManager = self.i18n  # type: ignore[attr-defined]
        header = i18n.t("grounding_sources_header")
        lines = [header]

        for source in sources:
            uri = source.get("uri", "")
            title = source.get("title", "")
            if title:
                lines.append(f"- [{title}](<{uri}>)")
            else:
                lines.append(f"- <{uri}>")

        return "\n".join(lines)

    # =========================================================================
    # Gemini API Retry Helper
    # =========================================================================

    async def _call_gemini_with_retry(self, **kwargs: Any) -> Any:
        """Call Gemini generate_content with retry logic for server/timeout errors.

        Args:
            **kwargs: Arguments passed to generate_content (model, config, contents).

        Returns:
            Gemini API response.

        Raises:
            Exception: The last exception if all retries are exhausted.
        """
        gemini_client: genai.Client = self.gemini_client  # type: ignore[attr-defined]
        last_exception: Exception | None = None

        for attempt in range(self._MAX_API_RETRIES + 1):
            try:
                return await gemini_client.aio.models.generate_content(**kwargs)
            except Exception as e:
                error_str = str(e)
                is_retryable = any(
                    pattern in error_str for pattern in self._RETRYABLE_ERROR_PATTERNS
                )

                if is_retryable and attempt < self._MAX_API_RETRIES:
                    delay = self._INITIAL_RETRY_DELAY * (2 ** attempt)
                    print(
                        f"Retryable API error (attempt {attempt + 1}/{self._MAX_API_RETRIES}): {e}"
                    )
                    print(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    last_exception = e
                else:
                    raise

        assert last_exception is not None
        raise last_exception

    # =========================================================================
    # ask_gemini Main Method
    # =========================================================================

    async def ask_gemini(
        self,
        channel_id: int,
        prompt: str,
        images: list[tuple[bytes, str]] | None = None,
        user_id: int | None = None,
    ) -> str:
        """Send a prompt to Gemini and return the response.

        Args:
            channel_id: Discord channel ID.
            prompt: Text prompt from user.
            images: Optional list of (image_data, mime_type) tuples.
            user_id: Discord user ID (for calendar integration).

        Returns:
            Response text from Gemini.
        """
        history_manager: HistoryManager = self.history_manager  # type: ignore[attr-defined]
        i18n: I18nManager = self.i18n  # type: ignore[attr-defined]
        gemini_client: genai.Client = self.gemini_client  # type: ignore[attr-defined]

        # Initialize conversation history for this channel if not exists
        if channel_id not in self.conversation_history:  # type: ignore[attr-defined]
            self.conversation_history[channel_id] = []  # type: ignore[attr-defined]

        # Load and add thought signature to history if exists and model not disabled
        model = self.get_model(channel_id)  # type: ignore[attr-defined]
        if not history_manager.is_model_disabled(model):
            thought_signature = history_manager.load_thought_signature(channel_id)
            if thought_signature:
                self.conversation_history[channel_id].append(  # type: ignore[attr-defined]
                    types.Content(
                        role="user",
                        parts=[types.Part(thought_signature=thought_signature)],
                    )
                )

        # Build and add user message to history
        user_content = self._build_user_content(prompt, images)
        self.conversation_history[channel_id].append(user_content)  # type: ignore[attr-defined]

        try:
            # Build configuration
            model = self.get_model(channel_id)  # type: ignore[attr-defined]
            config_params: dict[str, Any] = {
                "system_instruction": self._build_system_prompt(channel_id),
                "tools": self._get_tools_for_mode(channel_id),
            }

            # Only enable thinking config for models not disabled
            if not history_manager.is_model_disabled(model):
                config_params["thinking_config"] = types.ThinkingConfig(
                    include_thoughts=True
                )

            config_params.update(history_manager.load_generation_config(channel_id))

            # Call Gemini API with retry logic for thought signature errors
            try:
                response = await self._call_gemini_with_retry(
                    model=model,
                    config=types.GenerateContentConfig(**config_params),
                    contents=self.conversation_history[channel_id],  # type: ignore[attr-defined]
                )
            except Exception as e:
                error_str = str(e)
                is_thought_signature_error = (
                    "400 INVALID_ARGUMENT" in error_str
                    and "parts[0].data" in error_str
                    and "required oneof" in error_str
                )

                if is_thought_signature_error and not history_manager.is_model_disabled(
                    model
                ):
                    # thoughtSignature caused an error - disable it
                    history_manager.save_disabled_model(model)

                    # Remove the thought signature entry from history
                    if self.conversation_history[channel_id]:  # type: ignore[attr-defined]
                        last_entry = self.conversation_history[channel_id][-1]  # type: ignore[attr-defined]
                        if (
                            last_entry.role == "user"
                            and last_entry.parts
                            and len(last_entry.parts) == 1
                            and hasattr(last_entry.parts[0], "thought_signature")
                            and last_entry.parts[0].thought_signature is not None
                        ):
                            self.conversation_history[channel_id].pop()  # type: ignore[attr-defined]

                    # Retry without thinking config
                    config_params["thinking_config"] = types.ThinkingConfig(
                        include_thoughts=False
                    )
                    try:
                        response = await self._call_gemini_with_retry(
                            model=model,
                            config=types.GenerateContentConfig(**config_params),
                            contents=self.conversation_history[channel_id],  # type: ignore[attr-defined]
                        )
                    except Exception:
                        # If retry also fails, re-raise the original exception
                        raise
                else:
                    raise

            # Extract and save new thought signature
            new_signature = self._extract_thought_signature(response)
            if new_signature:
                history_manager.save_thought_signature(channel_id, new_signature)

            # Extract thought process text if enabled
            show_thought = history_manager.load_show_thought(channel_id)
            thought_text = None
            if show_thought:
                thought_text = self._extract_thought_text(response)

            # Process response (handle function calls if in calendar or todo mode)
            tool_mode = self.get_tool_mode(channel_id)  # type: ignore[attr-defined]
            if tool_mode in ("calendar", "todo"):
                response_text = await self._process_response(
                    response, channel_id, model, config_params, user_id
                )
            else:
                # Default mode: extract response text and append grounding sources
                response_text = response.text or ""

                # Extract and append grounding sources for default (search) mode
                grounding_sources = await self._extract_grounding_sources(response)
                if grounding_sources:
                    sources_text = self._format_grounding_sources(grounding_sources)
                    response_text = response_text + sources_text

            # Prepend thought process as spoiler if enabled
            if thought_text:
                thought_header = i18n.t("thought_process_header")
                response_text = (
                    f"||{thought_header}\n\n{thought_text}||\n\n{response_text}"
                )

            # Append usage cost if enabled
            show_usage = history_manager.load_show_usage(channel_id)
            if show_usage:
                usage_text = self._format_usage_cost(  # type: ignore[attr-defined]
                    response.usage_metadata, model
                )
                response_text = response_text + usage_text

            # Add model's response to history
            self.conversation_history[channel_id].append(  # type: ignore[attr-defined]
                types.Content(
                    role="model", parts=[types.Part.from_text(text=response_text)]
                )
            )

            # Save to disk with Git commit
            self._save_history_to_disk(channel_id)  # type: ignore[attr-defined]

            return response_text
        except Exception as e:
            # Remove the last user message from history if an error occurred
            if self.conversation_history[channel_id]:  # type: ignore[attr-defined]
                self.conversation_history[channel_id].pop()  # type: ignore[attr-defined]
            raise e

    # =========================================================================
    # _process_response Helper Methods
    # =========================================================================

    # Function name to handler mapping
    _CALENDAR_FUNCTIONS: frozenset[str] = frozenset({
        "list_calendar_events",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
    })

    _TASKS_FUNCTIONS: frozenset[str] = frozenset({
        "list_task_lists",
        "list_tasks",
        "create_task",
        "update_task",
        "complete_task",
        "delete_task",
    })

    def _extract_function_calls(self, response: Any) -> list:
        """Extract function calls from Gemini response.

        Args:
            response: Gemini API response.

        Returns:
            List of function call objects, empty if none found.
        """
        # Early returns for invalid response structure
        if not response.candidates:
            return []

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            return []

        # Collect function calls
        return [
            part.function_call
            for part in candidate.content.parts
            if hasattr(part, "function_call") and part.function_call
        ]

    async def _execute_function_calls(
        self,
        function_calls: list,
        user_id: int | None,
    ) -> list:
        """Execute multiple function calls and return response parts.

        Args:
            function_calls: List of function call objects.
            user_id: Discord user ID.

        Returns:
            List of function response Part objects.
        """
        responses = []
        for fc in function_calls:
            result = await self._execute_single_function(fc, user_id)
            responses.append(
                types.Part.from_function_response(name=fc.name, response=result)
            )
        return responses

    async def _execute_single_function(
        self,
        function_call: Any,
        user_id: int | None,
    ) -> dict:
        """Execute a single function call and return the result.

        Args:
            function_call: Function call object from Gemini.
            user_id: Discord user ID.

        Returns:
            Function result dictionary.
        """
        function_name = function_call.name
        function_args = dict(function_call.args) if function_call.args else {}

        # Route to appropriate handler
        if function_name in self._CALENDAR_FUNCTIONS:
            return await self._handle_calendar_function(
                function_name, function_args, user_id
            )

        if function_name in self._TASKS_FUNCTIONS:
            return await self._handle_tasks_function(
                function_name, function_args, user_id
            )

        return {"error": f"Unknown function: {function_name}"}

    async def _handle_calendar_function(
        self,
        function_name: str,
        function_args: dict,
        user_id: int | None,
    ) -> dict:
        """Handle calendar function calls.

        Args:
            function_name: Name of the calendar function.
            function_args: Arguments for the function.
            user_id: Discord user ID.

        Returns:
            Function result dictionary.
        """
        calendar_tool_handler: CalendarToolHandler | None = self.calendar_tool_handler  # type: ignore[attr-defined]
        if not calendar_tool_handler:
            return {"error": "Calendar integration not configured"}
        if not user_id:
            return {"error": "User ID not available"}

        return await calendar_tool_handler.handle_function_call(
            function_name, function_args, user_id
        )

    async def _handle_tasks_function(
        self,
        function_name: str,
        function_args: dict,
        user_id: int | None,
    ) -> dict:
        """Handle tasks function calls.

        Args:
            function_name: Name of the tasks function.
            function_args: Arguments for the function.
            user_id: Discord user ID.

        Returns:
            Function result dictionary.
        """
        tasks_tool_handler: TasksToolHandler | None = self.tasks_tool_handler  # type: ignore[attr-defined]
        if not tasks_tool_handler:
            return {"error": "Tasks integration not configured"}
        if not user_id:
            return {"error": "User ID not available"}

        return await tasks_tool_handler.handle_function_call(
            function_name, function_args, user_id
        )

    def _update_history_with_function_calls(
        self,
        channel_id: int,
        model_content: Any,
        function_responses: list,
    ) -> None:
        """Update conversation history with function call and responses.

        Args:
            channel_id: Discord channel ID.
            model_content: Model's content containing function calls.
            function_responses: List of function response Part objects.
        """
        # Add model's function call to history
        self.conversation_history[channel_id].append(model_content)  # type: ignore[attr-defined]

        # Add function responses to history
        self.conversation_history[channel_id].append(  # type: ignore[attr-defined]
            types.Content(role="user", parts=function_responses)
        )

    async def _process_response(
        self,
        response: Any,
        channel_id: int,
        model: str,
        config_params: dict,
        user_id: int | None,
    ) -> str:
        """Process Gemini response, handling function calls if present.

        Uses early return pattern for cleaner control flow.
        Recursively processes chained function calls.

        Args:
            response: Gemini API response.
            channel_id: Discord channel ID.
            model: Model name.
            config_params: Generation config parameters.
            user_id: Discord user ID.

        Returns:
            Final response text.
        """
        gemini_client: genai.Client = self.gemini_client  # type: ignore[attr-defined]

        # Extract function calls (empty list if none)
        function_calls = self._extract_function_calls(response)

        # No function calls - return text response
        if not function_calls:
            return response.text or ""

        # Execute all function calls
        function_responses = await self._execute_function_calls(
            function_calls, user_id
        )

        # Update history with function calls and responses
        self._update_history_with_function_calls(
            channel_id,
            response.candidates[0].content,
            function_responses,
        )

        # Get follow-up response from Gemini
        final_response = await self._call_gemini_with_retry(
            model=model,
            config=types.GenerateContentConfig(**config_params),
            contents=self.conversation_history[channel_id],  # type: ignore[attr-defined]
        )

        # Recursively process in case of chained function calls
        return await self._process_response(
            final_response, channel_id, model, config_params, user_id
        )
