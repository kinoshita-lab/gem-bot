"""Google Calendar tools for Gemini Function Calling.

This module defines the function declarations and handlers for
Google Calendar integration with Gemini API.
"""

from datetime import datetime, timedelta, timezone
from google.genai import types

from calendar_manager import CalendarAuthManager


def get_calendar_tools() -> list[types.Tool]:
    """Get the list of calendar tools for Gemini.

    Returns:
        List of Tool objects for calendar operations.
    """
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_calendar_events",
                    description="ユーザーのGoogle Calendarから予定を取得する。今日の予定、明日の予定、今週の予定などを確認するときに使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "time_min": types.Schema(
                                type=types.Type.STRING,
                                description="取得開始日時 (ISO 8601形式、例: 2024-01-15T00:00:00+09:00)。省略時は現在時刻。",
                            ),
                            "time_max": types.Schema(
                                type=types.Type.STRING,
                                description="取得終了日時 (ISO 8601形式)。省略時は制限なし。",
                            ),
                            "max_results": types.Schema(
                                type=types.Type.INTEGER,
                                description="取得する最大件数 (デフォルト: 10)",
                            ),
                        },
                        required=[],
                    ),
                ),
                types.FunctionDeclaration(
                    name="create_calendar_event",
                    description="Google Calendarに新しい予定を作成する。会議、イベント、リマインダーなどを追加するときに使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "summary": types.Schema(
                                type=types.Type.STRING,
                                description="予定のタイトル",
                            ),
                            "start_time": types.Schema(
                                type=types.Type.STRING,
                                description="開始日時 (ISO 8601形式、例: 2024-01-15T10:00:00+09:00) または日付のみ (例: 2024-01-15)",
                            ),
                            "end_time": types.Schema(
                                type=types.Type.STRING,
                                description="終了日時 (ISO 8601形式) または日付のみ。終日イベントの場合は翌日の日付を指定。",
                            ),
                            "description": types.Schema(
                                type=types.Type.STRING,
                                description="予定の詳細説明 (オプション)",
                            ),
                            "location": types.Schema(
                                type=types.Type.STRING,
                                description="予定の場所 (オプション)",
                            ),
                        },
                        required=["summary", "start_time", "end_time"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="update_calendar_event",
                    description="既存の予定を更新する。予定の時間変更、タイトル変更などに使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "event_id": types.Schema(
                                type=types.Type.STRING,
                                description="更新する予定のID",
                            ),
                            "summary": types.Schema(
                                type=types.Type.STRING,
                                description="新しいタイトル (変更する場合のみ)",
                            ),
                            "start_time": types.Schema(
                                type=types.Type.STRING,
                                description="新しい開始日時 (変更する場合のみ)",
                            ),
                            "end_time": types.Schema(
                                type=types.Type.STRING,
                                description="新しい終了日時 (変更する場合のみ)",
                            ),
                            "description": types.Schema(
                                type=types.Type.STRING,
                                description="新しい詳細説明 (変更する場合のみ)",
                            ),
                            "location": types.Schema(
                                type=types.Type.STRING,
                                description="新しい場所 (変更する場合のみ)",
                            ),
                        },
                        required=["event_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="delete_calendar_event",
                    description="予定を削除する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "event_id": types.Schema(
                                type=types.Type.STRING,
                                description="削除する予定のID",
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

    def __init__(self, calendar_auth: CalendarAuthManager):
        """Initialize the handler.

        Args:
            calendar_auth: CalendarAuthManager instance.
        """
        self.calendar_auth = calendar_auth

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
                "message": "Googleアカウントが連携されていません。`!calendar link` で連携してください。",
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
            return {"events": [], "message": "予定はありません。"}

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
            "message": f"予定「{event['summary']}」を作成しました。",
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
            "message": f"予定「{event['summary']}」を更新しました。",
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
            "message": "予定を削除しました。",
        }
