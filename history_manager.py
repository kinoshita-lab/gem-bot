"""
History Manager - Git-based conversation history management.

Manages conversation history with Git version control, enabling
branch/merge/fork operations for AI chat histories.

Each channel has its own independent Git repository.
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryManager:
    """Manages conversation history with Git version control.

    Each channel has its own Git repository at `base_dir/{channel_id}/`.
    """

    def __init__(self, base_dir: str = "history"):
        """Initialize the HistoryManager.

        Args:
            base_dir: Base directory for all channel repositories.
        """
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_repo_path(self, channel_id: int) -> Path:
        """Get the repository path for a channel.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the channel's Git repository.
        """
        return self.base_dir / str(channel_id)

    def _get_conversation_path(self, channel_id: int) -> Path:
        """Get the path to a conversation file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the conversation JSON file.
        """
        return self._get_repo_path(channel_id) / "conversation.json"

    def _ensure_repo(self, channel_id: int) -> Path:
        """Ensure the channel's Git repository exists.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the channel's repository.
        """
        repo_path = self._get_repo_path(channel_id)
        repo_path.mkdir(parents=True, exist_ok=True)

        if not (repo_path / ".git").exists():
            self._git(channel_id, "init")

        return repo_path

    def _git(
        self, channel_id: int, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess:
        """Execute a git command in the channel's repository.

        Args:
            channel_id: Discord channel ID.
            *args: Git command arguments.
            check: Whether to raise an exception on non-zero exit code.

        Returns:
            CompletedProcess instance with command results.
        """
        repo_path = self._get_repo_path(channel_id)
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if check and result.returncode != 0:
            raise RuntimeError(
                f"Git command failed: git {' '.join(args)}\n{result.stderr}"
            )
        return result

    def load_conversation(self, channel_id: int) -> dict[str, Any] | None:
        """Load conversation history from file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Conversation data dict or None if not found.
        """
        path = self._get_conversation_path(channel_id)
        if not path.exists():
            return None

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_conversation(
        self,
        channel_id: int,
        messages: list[dict[str, Any]],
        model: str,
        auto_commit: bool = True,
    ) -> None:
        """Save conversation history to file.

        Args:
            channel_id: Discord channel ID.
            messages: List of message dictionaries with role, content, timestamp.
            model: Model name used for the conversation.
            auto_commit: Whether to automatically commit changes.
        """
        self._ensure_repo(channel_id)
        path = self._get_conversation_path(channel_id)

        now = datetime.now(timezone.utc).isoformat()

        # Load existing data or create new
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["updated_at"] = now
            data["messages"] = messages
            data["model"] = model
        else:
            data = {
                "channel_id": channel_id,
                "model": model,
                "created_at": now,
                "updated_at": now,
                "messages": messages,
            }

        # Write to file
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if auto_commit:
            self.commit(channel_id, f"Update conversation")

    def clear_conversation(self, channel_id: int, auto_commit: bool = True) -> None:
        """Clear all conversation history for a channel.

        Args:
            channel_id: Discord channel ID.
            auto_commit: Whether to automatically commit changes.
        """
        self._ensure_repo(channel_id)
        path = self._get_conversation_path(channel_id)

        if path.exists():
            # Save empty messages list
            now = datetime.now(timezone.utc).isoformat()
            data = {
                "channel_id": channel_id,
                "model": "",
                "created_at": now,
                "updated_at": now,
                "messages": [],
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            if auto_commit:
                self.commit(channel_id, "Clear conversation history")

    def commit(self, channel_id: int, message: str) -> bool:
        """Commit current changes to Git.

        Args:
            channel_id: Discord channel ID.
            message: Commit message.

        Returns:
            True if commit was made, False if nothing to commit.
        """
        self._ensure_repo(channel_id)

        # Stage all changes
        self._git(channel_id, "add", "-A")

        # Check if there are changes to commit
        result = self._git(channel_id, "status", "--porcelain", check=False)
        if not result.stdout.strip():
            return False  # Nothing to commit

        # Commit
        self._git(channel_id, "commit", "-m", message)
        return True

    def get_current_branch(self, channel_id: int) -> str:
        """Get the name of the current branch.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Current branch name.
        """
        self._ensure_repo(channel_id)
        result = self._git(channel_id, "branch", "--show-current")
        return result.stdout.strip()

    def list_branches(self, channel_id: int) -> list[str]:
        """List all branches.

        Args:
            channel_id: Discord channel ID.

        Returns:
            List of branch names.
        """
        self._ensure_repo(channel_id)
        result = self._git(channel_id, "branch", "--list", "--format=%(refname:short)")
        branches = result.stdout.strip().split("\n")
        return [b for b in branches if b]

    def create_branch(
        self, channel_id: int, branch_name: str, switch: bool = False
    ) -> None:
        """Create a new branch from the current state.

        Args:
            channel_id: Discord channel ID.
            branch_name: Name for the new branch.
            switch: If True, switch to the new branch after creation.

        Raises:
            RuntimeError: If branch already exists.
        """
        self._ensure_repo(channel_id)

        # Check if branch already exists
        existing = self.list_branches(channel_id)
        if branch_name in existing:
            raise RuntimeError(f"ブランチ '{branch_name}' は既に存在します")

        self._git(channel_id, "branch", branch_name)

        if switch:
            self._git(channel_id, "checkout", branch_name)

    def switch_branch(self, channel_id: int, branch_name: str) -> None:
        """Switch to a different branch.

        Args:
            channel_id: Discord channel ID.
            branch_name: Name of the branch to switch to.
        """
        self._ensure_repo(channel_id)
        # Commit any uncommitted changes first
        self.commit(channel_id, "Auto-save before branch switch")
        self._git(channel_id, "checkout", branch_name)

    def get_log(self, channel_id: int, limit: int = 10) -> list[dict[str, str]]:
        """Get commit history.

        Args:
            channel_id: Discord channel ID.
            limit: Maximum number of commits to return.

        Returns:
            List of commit info dicts with hash, message, date, author.
        """
        self._ensure_repo(channel_id)
        result = self._git(
            channel_id,
            "log",
            f"-{limit}",
            "--format=%H|%s|%ai|%an",
            check=False,
        )
        if not result.stdout.strip():
            return []

        commits = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("|", 3)
                if len(parts) == 4:
                    commits.append(
                        {
                            "hash": parts[0],
                            "message": parts[1],
                            "date": parts[2],
                            "author": parts[3],
                        }
                    )
        return commits

    def convert_to_serializable(self, history: list) -> list[dict[str, Any]]:
        """Convert Gemini Content objects to serializable dicts.

        Args:
            history: List of Gemini Content objects.

        Returns:
            List of serializable message dicts.
        """
        messages = []
        for content in history:
            role = content.role
            # Extract text from parts
            text_parts = []
            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)

            messages.append(
                {
                    "role": role,
                    "content": "\n".join(text_parts),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        return messages

    def convert_from_serializable(
        self, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert serializable dicts back to a format usable by Gemini.

        Args:
            messages: List of message dicts from JSON.

        Returns:
            List of dicts with role and parts for Gemini API.
        """
        return [
            {
                "role": msg["role"],
                "content": msg["content"],
            }
            for msg in messages
        ]

    def load_all_conversations(self) -> dict[int, list[dict[str, Any]]]:
        """Load all conversation histories.

        Returns:
            Dict mapping channel_id to list of messages.
        """
        conversations = {}
        if not self.base_dir.exists():
            return conversations

        for channel_dir in self.base_dir.iterdir():
            if channel_dir.is_dir() and channel_dir.name.isdigit():
                # Check if it's a git repo with a conversation file
                if (channel_dir / ".git").exists():
                    channel_id = int(channel_dir.name)
                    data = self.load_conversation(channel_id)
                    if data and "messages" in data:
                        conversations[channel_id] = data["messages"]

        return conversations

    def list_channels(self) -> list[int]:
        """List all channel IDs with conversation histories.

        Returns:
            List of channel IDs.
        """
        channels = []
        if not self.base_dir.exists():
            return channels

        for channel_dir in self.base_dir.iterdir():
            if (
                channel_dir.is_dir()
                and channel_dir.name.isdigit()
                and (channel_dir / ".git").exists()
            ):
                channels.append(int(channel_dir.name))

        return channels

    def get_system_prompt_path(self, channel_id: int) -> Path:
        """Get the path to the system prompt file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the GEMINI.md file.
        """
        return self._get_repo_path(channel_id) / "GEMINI.md"

    def load_system_prompt(self, channel_id: int) -> str:
        """Load system prompt from file. Create empty file if not exists.

        Args:
            channel_id: Discord channel ID.

        Returns:
            System prompt content.
        """
        self._ensure_repo(channel_id)
        path = self.get_system_prompt_path(channel_id)

        if not path.exists():
            # Create empty file
            path.write_text("", encoding="utf-8")
            self.commit(channel_id, "Initialize empty system prompt")

        return path.read_text(encoding="utf-8")

    def save_system_prompt(
        self, channel_id: int, content: str, auto_commit: bool = True
    ) -> None:
        """Save system prompt to file.

        Args:
            channel_id: Discord channel ID.
            content: System prompt content.
            auto_commit: Whether to automatically commit changes.
        """
        self._ensure_repo(channel_id)
        path = self.get_system_prompt_path(channel_id)
        path.write_text(content, encoding="utf-8")

        if auto_commit:
            self.commit(channel_id, "Update system prompt")

    def _get_config_path(self, channel_id: int) -> Path:
        """Get the path to the config file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the config.json file.
        """
        return self._get_repo_path(channel_id) / "config.json"

    def load_model(self, channel_id: int, default_model: str) -> str:
        """Load model name from config file.

        Args:
            channel_id: Discord channel ID.
            default_model: Default model name if not configured.

        Returns:
            Model name.
        """
        self._ensure_repo(channel_id)
        path = self._get_config_path(channel_id)

        if not path.exists():
            return default_model

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data.get("model", default_model)

    def save_model(self, channel_id: int, model: str, auto_commit: bool = True) -> None:
        """Save model name to config file.

        Args:
            channel_id: Discord channel ID.
            model: Model name.
            auto_commit: Whether to automatically commit changes.
        """
        self._ensure_repo(channel_id)
        path = self._get_config_path(channel_id)

        # Load existing config or create new
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        data["model"] = model

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if auto_commit:
            self.commit(channel_id, f"Set model to {model}")
