"""Google Tasks tools for Gemini Function Calling.

This module defines the function declarations and handlers for
Google Tasks integration with Gemini API.
"""

from google.genai import types

from calendar_manager import CalendarAuthManager


def get_tasks_tools() -> list[types.Tool]:
    """Get the list of tasks tools for Gemini.

    Returns:
        List of Tool objects for tasks operations.
    """
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_task_lists",
                    description="ユーザーのGoogle Tasksのタスクリスト一覧を取得する。どのリストがあるか確認するときに使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "max_results": types.Schema(
                                type=types.Type.INTEGER,
                                description="取得する最大件数 (デフォルト: 10)",
                            ),
                        },
                        required=[],
                    ),
                ),
                types.FunctionDeclaration(
                    name="list_tasks",
                    description="タスクリストからタスク一覧を取得する。TODOリストの確認、やるべきことの確認に使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description="タスクリストID。省略時はデフォルトのリスト(@default)を使用。",
                            ),
                            "show_completed": types.Schema(
                                type=types.Type.BOOLEAN,
                                description="完了済みタスクを表示するか (デフォルト: false)",
                            ),
                            "max_results": types.Schema(
                                type=types.Type.INTEGER,
                                description="取得する最大件数 (デフォルト: 100)",
                            ),
                        },
                        required=[],
                    ),
                ),
                types.FunctionDeclaration(
                    name="create_task",
                    description="新しいタスクを作成する。TODOの追加、やることリストへの追加に使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "title": types.Schema(
                                type=types.Type.STRING,
                                description="タスクのタイトル",
                            ),
                            "notes": types.Schema(
                                type=types.Type.STRING,
                                description="タスクの詳細メモ (オプション)",
                            ),
                            "due": types.Schema(
                                type=types.Type.STRING,
                                description="期限日 (RFC 3339形式、例: 2024-01-15T00:00:00.000Z)。日付のみの場合はT00:00:00.000Zを付加。",
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description="タスクリストID。省略時はデフォルトのリストを使用。",
                            ),
                        },
                        required=["title"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="update_task",
                    description="既存のタスクを更新する。タスクの内容変更、期限変更などに使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "task_id": types.Schema(
                                type=types.Type.STRING,
                                description="更新するタスクのID",
                            ),
                            "title": types.Schema(
                                type=types.Type.STRING,
                                description="新しいタイトル (変更する場合のみ)",
                            ),
                            "notes": types.Schema(
                                type=types.Type.STRING,
                                description="新しいメモ (変更する場合のみ)",
                            ),
                            "due": types.Schema(
                                type=types.Type.STRING,
                                description="新しい期限日 (変更する場合のみ)",
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description="タスクリストID。省略時はデフォルトのリストを使用。",
                            ),
                        },
                        required=["task_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="complete_task",
                    description="タスクを完了にする。TODOを終わらせた、タスクが完了したときに使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "task_id": types.Schema(
                                type=types.Type.STRING,
                                description="完了にするタスクのID",
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description="タスクリストID。省略時はデフォルトのリストを使用。",
                            ),
                        },
                        required=["task_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="delete_task",
                    description="タスクを削除する。不要になったタスクの削除に使用する。",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "task_id": types.Schema(
                                type=types.Type.STRING,
                                description="削除するタスクのID",
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description="タスクリストID。省略時はデフォルトのリストを使用。",
                            ),
                        },
                        required=["task_id"],
                    ),
                ),
            ]
        )
    ]


class TasksToolHandler:
    """Handles tasks tool calls from Gemini."""

    def __init__(self, calendar_auth: CalendarAuthManager):
        """Initialize the handler.

        Args:
            calendar_auth: CalendarAuthManager instance (also handles Tasks).
        """
        self.calendar_auth = calendar_auth

    async def handle_function_call(
        self,
        function_name: str,
        function_args: dict,
        user_id: int,
    ) -> dict:
        """Handle a tasks function call.

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
            if function_name == "list_task_lists":
                return await self._handle_list_task_lists(user_id, function_args)
            elif function_name == "list_tasks":
                return await self._handle_list_tasks(user_id, function_args)
            elif function_name == "create_task":
                return await self._handle_create_task(user_id, function_args)
            elif function_name == "update_task":
                return await self._handle_update_task(user_id, function_args)
            elif function_name == "complete_task":
                return await self._handle_complete_task(user_id, function_args)
            elif function_name == "delete_task":
                return await self._handle_delete_task(user_id, function_args)
            else:
                return {"error": "unknown_function", "message": f"Unknown function: {function_name}"}
        except Exception as e:
            return {"error": "api_error", "message": str(e)}

    async def _handle_list_task_lists(self, user_id: int, args: dict) -> dict:
        """Handle list_task_lists function call."""
        task_lists = await self.calendar_auth.list_task_lists(
            user_id=user_id,
            max_results=args.get("max_results", 10),
        )

        if not task_lists:
            return {"task_lists": [], "message": "タスクリストがありません。"}

        return {"task_lists": task_lists, "count": len(task_lists)}

    async def _handle_list_tasks(self, user_id: int, args: dict) -> dict:
        """Handle list_tasks function call."""
        tasks = await self.calendar_auth.list_tasks(
            user_id=user_id,
            tasklist_id=args.get("tasklist_id", "@default"),
            show_completed=args.get("show_completed", False),
            max_results=args.get("max_results", 100),
        )

        if not tasks:
            return {"tasks": [], "message": "タスクはありません。"}

        return {"tasks": tasks, "count": len(tasks)}

    async def _handle_create_task(self, user_id: int, args: dict) -> dict:
        """Handle create_task function call."""
        task = await self.calendar_auth.create_task(
            user_id=user_id,
            title=args["title"],
            notes=args.get("notes", ""),
            due=args.get("due"),
            tasklist_id=args.get("tasklist_id", "@default"),
        )

        return {
            "success": True,
            "message": f"タスク「{task['title']}」を作成しました。",
            "task": task,
        }

    async def _handle_update_task(self, user_id: int, args: dict) -> dict:
        """Handle update_task function call."""
        task = await self.calendar_auth.update_task(
            user_id=user_id,
            task_id=args["task_id"],
            title=args.get("title"),
            notes=args.get("notes"),
            due=args.get("due"),
            tasklist_id=args.get("tasklist_id", "@default"),
        )

        return {
            "success": True,
            "message": f"タスク「{task['title']}」を更新しました。",
            "task": task,
        }

    async def _handle_complete_task(self, user_id: int, args: dict) -> dict:
        """Handle complete_task function call."""
        task = await self.calendar_auth.complete_task(
            user_id=user_id,
            task_id=args["task_id"],
            tasklist_id=args.get("tasklist_id", "@default"),
        )

        return {
            "success": True,
            "message": f"タスク「{task['title']}」を完了にしました。",
            "task": task,
        }

    async def _handle_delete_task(self, user_id: int, args: dict) -> dict:
        """Handle delete_task function call."""
        await self.calendar_auth.delete_task(
            user_id=user_id,
            task_id=args["task_id"],
            tasklist_id=args.get("tasklist_id", "@default"),
        )

        return {
            "success": True,
            "message": "タスクを削除しました。",
        }
