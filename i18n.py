"""
I18n Manager - Internationalization support for the bot.

Manages language settings and translations with persistence in history/config.json.
"""

import json
from pathlib import Path
from typing import Any


class I18nManager:
    """Manages internationalization for the bot.

    Stores language setting in history/config.json and loads translations
    from locales/{lang}.json files. Supported languages are auto-detected
    from the locales directory.
    """

    DEFAULT_LANGUAGE = "ja"

    def __init__(self, config_dir: str = "history", locales_dir: str = "locales"):
        """Initialize the I18nManager.

        Args:
            config_dir: Directory for configuration file.
            locales_dir: Directory containing translation files.
        """
        self.config_dir = Path(config_dir).resolve()
        self.locales_dir = Path(locales_dir).resolve()
        self.config_path = self.config_dir / "config.json"

        # Ensure directories exist
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect supported languages from locales directory
        self._supported_languages: list[str] = self._detect_languages()

        # Load translations
        self._translations: dict[str, dict[str, str]] = {}
        self._load_translations()

        # Load configuration (after translations so we can validate language)
        self._config = self._load_config()

    def _detect_languages(self) -> list[str]:
        """Detect available languages from locales directory.

        Returns:
            List of language codes found in locales directory.
        """
        languages = []
        if self.locales_dir.exists():
            for lang_file in self.locales_dir.glob("*.json"):
                lang_code = lang_file.stem  # e.g., "ja" from "ja.json"
                languages.append(lang_code)

        # Sort for consistent ordering, but ensure default is available
        languages.sort()

        if not languages:
            print(f"Warning: No translation files found in {self.locales_dir}")
            # Return default as fallback
            return [self.DEFAULT_LANGUAGE]

        return languages

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary (full config including channels, etc.).
        """
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Validate that configured language is still available
                if config.get("language") not in self._supported_languages:
                    config["language"] = self._get_default_language()
                return config
        return {"language": self._get_default_language(), "channels": {}}

    def _get_default_language(self) -> str:
        """Get default language, preferring DEFAULT_LANGUAGE if available.

        Returns:
            Default language code.
        """
        if self.DEFAULT_LANGUAGE in self._supported_languages:
            return self.DEFAULT_LANGUAGE
        # Fall back to first available language
        return self._supported_languages[0] if self._supported_languages else "en"

    def _save_config(self) -> None:
        """Save configuration to file.

        Preserves existing keys (like channels) while updating language.
        """
        # Load existing config to preserve other keys
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                existing_config = json.load(f)
        else:
            existing_config = {}

        # Merge: update language while preserving other keys
        existing_config["language"] = self._config.get(
            "language", self._get_default_language()
        )

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(existing_config, f, ensure_ascii=False, indent=2)

    def _load_translations(self) -> None:
        """Load all translation files from locales directory."""
        for lang in self._supported_languages:
            lang_file = self.locales_dir / f"{lang}.json"
            if lang_file.exists():
                with open(lang_file, "r", encoding="utf-8") as f:
                    self._translations[lang] = json.load(f)
            else:
                self._translations[lang] = {}

    def reload_translations(self) -> None:
        """Reload translations from disk.

        Call this to pick up new language files without restarting.
        """
        self._supported_languages = self._detect_languages()
        self._translations.clear()
        self._load_translations()

        # Validate current language is still available
        if self.language not in self._supported_languages:
            self._config["language"] = self._get_default_language()
            self._save_config()

    @property
    def language(self) -> str:
        """Get current language.

        Returns:
            Current language code.
        """
        return self._config.get("language", self._get_default_language())

    @language.setter
    def language(self, value: str) -> None:
        """Set current language.

        Args:
            value: Language code to set.

        Raises:
            ValueError: If language is not supported.
        """
        if value not in self._supported_languages:
            raise ValueError(
                f"Unsupported language: {value}. "
                f"Supported: {', '.join(self._supported_languages)}"
            )
        self._config["language"] = value
        self._save_config()

    def t(self, key: str, **kwargs) -> str:
        """Get translated string.

        Args:
            key: Translation key.
            **kwargs: Format arguments for the translated string.

        Returns:
            Translated and formatted string.
        """
        lang = self.language
        translations = self._translations.get(lang, {})

        # Fallback to default language if key not found
        if key not in translations:
            default_lang = self._get_default_language()
            translations = self._translations.get(default_lang, {})

        text = translations.get(key, key)

        # Format with provided arguments
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError:
                pass  # Return unformatted if format fails

        return text

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes.

        Returns:
            List of language codes (auto-detected from locales directory).
        """
        return self._supported_languages.copy()
