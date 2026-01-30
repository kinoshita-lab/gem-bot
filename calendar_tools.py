"""Google Calendar tools for Gemini Function Calling.

This module defines the function declarations and handlers for
Google Calendar integration with Gemini API.
"""

from datetime import datetime, timedelta, timezone
from google.genai import types

from calendar_manager import CalendarAuthManager
from i18n import I18nManager


def get_calendar_tools(i18n: I18nManager) -> list[types.Tool]:
    """Get the list of calendar tools for Gemini.

    Args:
        i18n: I18nManager instance for translations.

    Returns:
        List of Tool objects for calendar operations.
    """
    t = i18n.t
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_calendar_events",
                    description=t("calendar_func_list_events_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "time_min": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_time_min"),
                            ),
                            "time_max": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_time_max"),
                            ),
                            "max_results": types.Schema(
                                type=types.Type.INTEGER,
                                description=t("calendar_param_max_results"),
                            ),
                        },
                        required=[],
                    ),
                ),
                types.FunctionDeclaration(
                    name="create_calendar_event",
                    description=t("calendar_func_create_event_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "summary": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_summary"),
                            ),
                            "start_time": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_start_time"),
                            ),
                            "end_time": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_end_time"),
                            ),
                            "description": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_description"),
                            ),
                            "location": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_location"),
                            ),
                        },
                        required=["summary", "start_time", "end_time"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="update_calendar_event",
                    description=t("calendar_func_update_event_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "event_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_event_id_update"),
                            ),
                            "summary": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_summary_new"),
                            ),
                            "start_time": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_start_time_new"),
                            ),
                            "end_time": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_end_time_new"),
                            ),
                            "description": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_description_new"),
                            ),
                            "location": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_location_new"),
                            ),
                        },
                        required=["event_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="delete_calendar_event",
                    description=t("calendar_func_delete_event_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "event_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("calendar_param_event_id_delete"),
                            ),
                        },
                        required=["event_id"],
                    ),
                ),
            ]
        )
    ]


class CalendarToolHandler:
    """Handles calendar tool calls from Gemini."""

    def __init__(self, calendar_auth: CalendarAuthManager, i18n: I18nManager):
        """Initialize the handler.

        Args:
            calendar_auth: CalendarAuthManager instance.
            i18n: I18nManager instance for translations.
        """
        self.calendar_auth = calendar_auth
        self.i18n = i18n

    def t(self, key: str, **kwargs) -> str:
        """Get translated string."""
        return self.i18n.t(key, **kwargs)

    async def handle_function_call(
        self,
        function_name: str,
        function_args: dict,
        user_id: int,
    ) -> dict:
        """Handle a calendar function call.

        Args:
            function_name: Name of the function to call.
            function_args: Arguments for the function.
            user_id: Discord user ID.

        Returns:
            Result dictionary with the function response.
        """
        # Check if user is authenticated
        if not self.calendar_auth.is_user_authenticated(user_id):
            return {
                "error": "not_authenticated",
                "message": self.t("calendar_not_authenticated"),
            }

        try:
            if function_name == "list_calendar_events":
                return await self._handle_list_events(user_id, function_args)
            elif function_name == "create_calendar_event":
                return await self._handle_create_event(user_id, function_args)
            elif function_name == "update_calendar_event":
                return await self._handle_update_event(user_id, function_args)
            elif function_name == "delete_calendar_event":
                return await self._handle_delete_event(user_id, function_args)
            else:
                return {"error": "unknown_function", "message": f"Unknown function: {function_name}"}
        except Exception as e:
            return {"error": "api_error", "message": str(e)}

    async def _handle_list_events(self, user_id: int, args: dict) -> dict:
        """Handle list_calendar_events function call."""
        events = await self.calendar_auth.list_events(
            user_id=user_id,
            time_min=args.get("time_min"),
            time_max=args.get("time_max"),
            max_results=args.get("max_results", 10),
        )

        if not events:
            return {"events": [], "message": self.t("calendar_events_empty")}

        return {"events": events, "count": len(events)}

    async def _handle_create_event(self, user_id: int, args: dict) -> dict:
        """Handle create_calendar_event function call."""
        event = await self.calendar_auth.create_event(
            user_id=user_id,
            summary=args["summary"],
            start_time=args["start_time"],
            end_time=args["end_time"],
            description=args.get("description", ""),
            location=args.get("location", ""),
        )

        return {
            "success": True,
            "message": self.t("calendar_created", summary=event["summary"]),
            "event": event,
        }

    async def _handle_update_event(self, user_id: int, args: dict) -> dict:
        """Handle update_calendar_event function call."""
        event = await self.calendar_auth.update_event(
            user_id=user_id,
            event_id=args["event_id"],
            summary=args.get("summary"),
            start_time=args.get("start_time"),
            end_time=args.get("end_time"),
            description=args.get("description"),
            location=args.get("location"),
        )

        return {
            "success": True,
            "message": self.t("calendar_updated", summary=event["summary"]),
            "event": event,
        }

    async def _handle_delete_event(self, user_id: int, args: dict) -> dict:
        """Handle delete_calendar_event function call."""
        await self.calendar_auth.delete_event(
            user_id=user_id,
            event_id=args["event_id"],
        )

        return {
            "success": True,
            "message": self.t("calendar_deleted"),
        }
