"""Google Tasks tools for Gemini Function Calling.

This module defines the function declarations and handlers for
Google Tasks integration with Gemini API.
"""

from google.genai import types

from calendar_manager import CalendarAuthManager
from i18n import I18nManager


def get_tasks_tools(i18n: I18nManager) -> list[types.Tool]:
    """Get the list of tasks tools for Gemini.

    Args:
        i18n: I18n instance for translations.

    Returns:
        List of Tool objects for tasks operations.
    """
    t = i18n.t
    return [
        types.Tool(
            function_declarations=[
                types.FunctionDeclaration(
                    name="list_task_lists",
                    description=t("tasks_func_list_task_lists_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "max_results": types.Schema(
                                type=types.Type.INTEGER,
                                description=t("tasks_param_max_results_10"),
                            ),
                        },
                        required=[],
                    ),
                ),
                types.FunctionDeclaration(
                    name="list_tasks",
                    description=t("tasks_func_list_tasks_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_tasklist_id"),
                            ),
                            "show_completed": types.Schema(
                                type=types.Type.BOOLEAN,
                                description=t("tasks_param_show_completed"),
                            ),
                            "max_results": types.Schema(
                                type=types.Type.INTEGER,
                                description=t("tasks_param_max_results_100"),
                            ),
                        },
                        required=[],
                    ),
                ),
                types.FunctionDeclaration(
                    name="create_task",
                    description=t("tasks_func_create_task_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "title": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_title"),
                            ),
                            "notes": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_notes"),
                            ),
                            "due": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_due"),
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_tasklist_id_default"),
                            ),
                        },
                        required=["title"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="update_task",
                    description=t("tasks_func_update_task_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "task_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_task_id_update"),
                            ),
                            "title": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_title_new"),
                            ),
                            "notes": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_notes_new"),
                            ),
                            "due": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_due_new"),
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_tasklist_id_default"),
                            ),
                        },
                        required=["task_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="complete_task",
                    description=t("tasks_func_complete_task_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "task_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_task_id_complete"),
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_tasklist_id_default"),
                            ),
                        },
                        required=["task_id"],
                    ),
                ),
                types.FunctionDeclaration(
                    name="delete_task",
                    description=t("tasks_func_delete_task_desc"),
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "task_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_task_id_delete"),
                            ),
                            "tasklist_id": types.Schema(
                                type=types.Type.STRING,
                                description=t("tasks_param_tasklist_id_default"),
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

    def __init__(self, calendar_auth: CalendarAuthManager, i18n: I18nManager):
        """Initialize the handler.

        Args:
            calendar_auth: CalendarAuthManager instance (also handles Tasks).
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
                "message": self.t("tasks_not_authenticated"),
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
            return {"task_lists": [], "message": self.t("tasks_list_empty")}

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
            return {"tasks": [], "message": self.t("tasks_empty")}

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
            "message": self.t("tasks_created", title=task["title"]),
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
            "message": self.t("tasks_updated", title=task["title"]),
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
            "message": self.t("tasks_completed", title=task["title"]),
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
            "message": self.t("tasks_deleted"),
        }
