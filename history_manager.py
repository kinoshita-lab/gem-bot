"""
History Manager - Git-based conversation history management.

Manages conversation history with Git version control, enabling
branch/merge/fork operations for AI chat histories.

Each channel has its own independent Git repository.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from i18n import I18nManager


class HistoryManager:
    """Manages conversation history with Git version control.

    Each channel has its own Git repository at `base_dir/{channel_id}/`.
    """

    def __init__(self, base_dir: str = "history", i18n: I18nManager | None = None):
        """Initialize the HistoryManager.

        Args:
            base_dir: Base directory for all channel repositories.
            i18n: I18nManager instance for translations (optional for backward compatibility).
        """
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.i18n = i18n

    def t(self, key: str, **kwargs) -> str:
        """Get translated string.

        Falls back to key if i18n is not available.
        """
        if self.i18n:
            return self.i18n.t(key, **kwargs)
        return key

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

    def _get_files_dir(self, channel_id: int) -> Path:
        """Get the files directory path for a channel.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the files directory.
        """
        return self._get_repo_path(channel_id) / "files"

    # MIME type to file extension mapping
    MIME_TO_EXT: dict[str, str] = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }

    # File extension to MIME type mapping
    EXT_TO_MIME: dict[str, str] = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }

    def save_image(self, channel_id: int, image_data: bytes, mime_type: str) -> str:
        """Save image to files directory and return relative path.

        Args:
            channel_id: Discord channel ID.
            image_data: Raw image bytes.
            mime_type: MIME type (e.g., "image/png").

        Returns:
            Relative path like "files/img_20240128_123456_001.png"
        """
        self._ensure_repo(channel_id)
        files_dir = self._get_files_dir(channel_id)
        files_dir.mkdir(parents=True, exist_ok=True)

        # Determine file extension
        ext = self.MIME_TO_EXT.get(mime_type, ".bin")

        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"img_{timestamp}"

        # Find unique filename with counter
        counter = 1
        while True:
            filename = f"{base_name}_{counter:03d}{ext}"
            file_path = files_dir / filename
            if not file_path.exists():
                break
            counter += 1

        # Write image data
        file_path.write_bytes(image_data)

        # Return relative path (from repo root)
        return f"files/{filename}"

    def load_image(self, channel_id: int, relative_path: str) -> tuple[bytes, str] | None:
        """Load image from files directory.

        Args:
            channel_id: Discord channel ID.
            relative_path: Relative path like "files/img_xxx.png"

        Returns:
            Tuple of (image_data, mime_type) or None if not found.
        """
        repo_path = self._get_repo_path(channel_id)
        file_path = repo_path / relative_path

        if not file_path.exists():
            return None

        # Determine MIME type from extension
        ext = file_path.suffix.lower()
        mime_type = self.EXT_TO_MIME.get(ext, "application/octet-stream")

        # Read and return image data
        image_data = file_path.read_bytes()
        return (image_data, mime_type)

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
            encoding="utf-8",
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
            raise RuntimeError(self.t("history_branch_already_exists", branch=branch_name))

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

    def delete_branch(self, channel_id: int, branch_name: str) -> None:
        """Delete a branch.

        Args:
            channel_id: Discord channel ID.
            branch_name: Name of the branch to delete.

        Raises:
            RuntimeError: If branch is 'main', current branch, or doesn't exist.
        """
        self._ensure_repo(channel_id)

        # Prevent deleting main branch
        if branch_name == "main":
            raise RuntimeError(self.t("history_cannot_delete_main"))

        # Prevent deleting current branch
        current = self.get_current_branch(channel_id)
        if branch_name == current:
            raise RuntimeError(self.t("history_cannot_delete_current"))

        # Check if branch exists
        branches = self.list_branches(channel_id)
        if branch_name not in branches:
            raise RuntimeError(self.t("history_branch_not_found", branch=branch_name))

        # Force delete the branch
        self._git(channel_id, "branch", "-D", branch_name)

    def merge_branch(
        self, channel_id: int, source_branch: str, auto_commit: bool = True
    ) -> int:
        """Merge messages from source branch into current branch.

        Only messages after the divergence point are merged.

        Args:
            channel_id: Discord channel ID.
            source_branch: Name of the branch to merge from.
            auto_commit: Whether to automatically commit changes.

        Returns:
            Number of messages merged.

        Raises:
            RuntimeError: If source branch doesn't exist or is current branch.
        """
        self._ensure_repo(channel_id)

        current_branch = self.get_current_branch(channel_id)
        if source_branch == current_branch:
            raise RuntimeError(self.t("history_cannot_merge_current"))

        branches = self.list_branches(channel_id)
        if source_branch not in branches:
            raise RuntimeError(self.t("history_branch_not_found", branch=source_branch))

        # Load current branch messages
        current_data = self.load_conversation(channel_id)
        current_messages = current_data.get("messages", []) if current_data else []

        # Switch to source branch and load its messages
        self._git(channel_id, "checkout", source_branch)
        source_data = self.load_conversation(channel_id)
        source_messages = source_data.get("messages", []) if source_data else []

        # Switch back to current branch
        self._git(channel_id, "checkout", current_branch)

        # Find divergence point
        divergence = self._find_divergence_point(current_messages, source_messages)

        # Get messages to merge (after divergence point)
        messages_to_merge = source_messages[divergence:]

        if not messages_to_merge:
            return 0

        # Append to current messages
        merged_messages = current_messages + messages_to_merge

        # Save merged conversation
        model = current_data.get("model", "") if current_data else ""
        self.save_conversation(channel_id, merged_messages, model, auto_commit=False)

        if auto_commit:
            self.commit(channel_id, f"Merge branch '{source_branch}'")

        return len(messages_to_merge)

    def _find_divergence_point(
        self, current: list[dict[str, Any]], source: list[dict[str, Any]]
    ) -> int:
        """Find the index where two message lists diverge.

        Args:
            current: Messages from current branch.
            source: Messages from source branch.

        Returns:
            Index of divergence point (first differing message).
        """
        divergence = 0
        for i, (curr, src) in enumerate(zip(current, source)):
            if curr.get("content") == src.get("content") and curr.get(
                "role"
            ) == src.get("role"):
                divergence = i + 1
            else:
                break
        return divergence

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

    def convert_to_serializable(
        self, history: list, channel_id: int | None = None
    ) -> list[dict[str, Any]]:
        """Convert Gemini Content objects to serializable dicts.

        Args:
            history: List of Gemini Content objects.
            channel_id: Discord channel ID (required if history contains images).

        Returns:
            List of serializable message dicts.
        """
        messages = []
        for content in history:
            role = content.role
            # Extract text and images from parts
            text_parts = []
            image_paths = []

            for part in content.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                elif hasattr(part, "inline_data") and part.inline_data:
                    # Save image and record path
                    if channel_id is not None:
                        path = self.save_image(
                            channel_id,
                            part.inline_data.data,
                            part.inline_data.mime_type,
                        )
                        image_paths.append(path)

            msg: dict[str, Any] = {
                "role": role,
                "content": "\n".join(text_parts),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if image_paths:
                msg["images"] = image_paths

            messages.append(msg)
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

    def get_channel_prompt_path(self, channel_id: int) -> Path:
        """Get the path to the channel instruction file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Path to the channel_instruction.md file.
        """
        return self._get_repo_path(channel_id) / "channel_instruction.md"

    def load_channel_prompt(self, channel_id: int) -> str:
        """Load channel-specific instruction from file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Channel instruction content.
        """
        self._ensure_repo(channel_id)
        path = self.get_channel_prompt_path(channel_id)

        if not path.exists():
            return ""

        return path.read_text(encoding="utf-8")

    def load_system_prompt(self, channel_id: int) -> str:
        """Load system prompt.

        Merges Master instruction (root GEMINI.md) and
        Channel instruction (channel_instruction.md).

        Args:
            channel_id: Discord channel ID.

        Returns:
            Combined system prompt content.
        """
        # Load Master Instruction (Optional)
        master_path = self.base_dir.parent / "GEMINI.md"
        master_content = ""
        if master_path.exists():
            try:
                master_content = master_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"Error reading master GEMINI.md: {e}")

        # Load Channel Instruction
        self._ensure_repo(channel_id)
        channel_path = self.get_channel_prompt_path(channel_id)
        channel_content = ""

        if channel_path.exists():
            channel_content = channel_path.read_text(encoding="utf-8")
        else:
            # Create empty file
            channel_path.write_text("", encoding="utf-8")
            self.commit(channel_id, "Initialize empty channel instruction")

        # Combine
        parts = []
        if master_content:
            parts.append(master_content)
        if channel_content:
            parts.append(channel_content)
            
        return "\n\n".join(parts)

    def save_system_prompt(
        self, channel_id: int, content: str, auto_commit: bool = True
    ) -> None:
        """Save channel instruction to file.

        Args:
            channel_id: Discord channel ID.
            content: Channel instruction content.
            auto_commit: Whether to automatically commit changes.
        """
        self._ensure_repo(channel_id)
        path = self.get_channel_prompt_path(channel_id)
        path.write_text(content, encoding="utf-8")

        if auto_commit:
            self.commit(channel_id, "Update channel instruction")

    def save_master_prompt(self, content: str) -> None:
        """Save master instruction to root GEMINI.md.

        Args:
            content: Master instruction content.
        """
        master_path = self.base_dir.parent / "GEMINI.md"
        master_path.write_text(content, encoding="utf-8")

    def _get_global_config_path(self) -> Path:
        """Get the path to the global config file.

        Returns:
            Path to history/config.json.
        """
        return self.base_dir / "config.json"

    def _load_global_config(self) -> dict[str, Any]:
        """Load global configuration from file.

        Returns:
            Configuration dictionary.
        """
        path = self._get_global_config_path()
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"channels": {}}

    def _save_global_config(self, config: dict[str, Any]) -> None:
        """Save global configuration to file.

        Args:
            config: Configuration dictionary.
        """
        path = self._get_global_config_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def load_model(self, channel_id: int, default_model: str) -> str:
        """Load model name from global config file.

        Args:
            channel_id: Discord channel ID.
            default_model: Default model name if not configured.

        Returns:
            Model name.
        """
        config = self._load_global_config()
        channels = config.get("channels", {})
        channel_config = channels.get(str(channel_id), {})
        return channel_config.get("model", default_model)

    def save_model(self, channel_id: int, model: str) -> None:
        """Save model name to global config file.

        Args:
            channel_id: Discord channel ID.
            model: Model name.
        """
        config = self._load_global_config()

        if "channels" not in config:
            config["channels"] = {}

        channel_key = str(channel_id)
        if channel_key not in config["channels"]:
            config["channels"][channel_key] = {}

        config["channels"][channel_key]["model"] = model
        self._save_global_config(config)

    # Valid generation config keys and their types/validators
    GENERATION_CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
        "temperature": {"type": float, "min": 0.0, "max": 2.0},
        "top_p": {"type": float, "min": 0.0, "max": 1.0},
        "top_k": {"type": int, "min": 1, "max": 100},
        "max_output_tokens": {"type": int, "min": 1, "max": 65536},
        "presence_penalty": {"type": float, "min": -2.0, "max": 2.0},
        "frequency_penalty": {"type": float, "min": -2.0, "max": 2.0},
    }

    def load_generation_config(self, channel_id: int) -> dict[str, Any]:
        """Load generation config from global config file.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Generation config dictionary (empty if not configured).
        """
        config = self._load_global_config()
        channels = config.get("channels", {})
        channel_config = channels.get(str(channel_id), {})
        return channel_config.get("generation_config", {})

    def save_generation_config_value(
        self, channel_id: int, key: str, value: Any
    ) -> None:
        """Save a single generation config value.

        Args:
            channel_id: Discord channel ID.
            key: Config key name.
            value: Config value.

        Raises:
            ValueError: If key is invalid or value is out of range.
        """
        if key not in self.GENERATION_CONFIG_SCHEMA:
            valid_keys = ", ".join(self.GENERATION_CONFIG_SCHEMA.keys())
            raise ValueError(self.t("history_config_invalid_key", key=key, valid_keys=valid_keys))

        schema = self.GENERATION_CONFIG_SCHEMA[key]
        expected_type = schema["type"]

        # Type conversion
        try:
            if expected_type == float:
                value = float(value)
            elif expected_type == int:
                value = int(value)
        except (ValueError, TypeError):
            raise ValueError(
                self.t("history_config_invalid_type", key=key, type_name=expected_type.__name__)
            )

        # Range validation
        if "min" in schema and value < schema["min"]:
            raise ValueError(self.t("history_config_min_value", key=key, min=schema["min"]))
        if "max" in schema and value > schema["max"]:
            raise ValueError(self.t("history_config_max_value", key=key, max=schema["max"]))

        config = self._load_global_config()

        if "channels" not in config:
            config["channels"] = {}

        channel_key = str(channel_id)
        if channel_key not in config["channels"]:
            config["channels"][channel_key] = {}

        if "generation_config" not in config["channels"][channel_key]:
            config["channels"][channel_key]["generation_config"] = {}

        config["channels"][channel_key]["generation_config"][key] = value
        self._save_global_config(config)

    def reset_generation_config(self, channel_id: int, key: str | None = None) -> None:
        """Reset generation config to default.

        Args:
            channel_id: Discord channel ID.
            key: Specific key to reset, or None to reset all.
        """
        config = self._load_global_config()
        channel_key = str(channel_id)

        if "channels" not in config:
            return
        if channel_key not in config["channels"]:
            return
        if "generation_config" not in config["channels"][channel_key]:
            return

        if key is None:
            # Reset all
            del config["channels"][channel_key]["generation_config"]
        else:
            # Reset specific key
            gen_config = config["channels"][channel_key]["generation_config"]
            if key in gen_config:
                del gen_config[key]
            # Clean up empty dict
            if not gen_config:
                del config["channels"][channel_key]["generation_config"]

        self._save_global_config(config)
