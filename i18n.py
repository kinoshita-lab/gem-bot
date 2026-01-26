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
    from locales/{lang}.json files.
    """

    SUPPORTED_LANGUAGES = ["ja", "en"]
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

        # Load configuration
        self._config = self._load_config()

        # Load translations
        self._translations: dict[str, dict[str, str]] = {}
        self._load_translations()

    def _load_config(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary.
        """
        if self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"language": self.DEFAULT_LANGUAGE}

    def _save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, ensure_ascii=False, indent=2)

    def _load_translations(self) -> None:
        """Load all translation files."""
        for lang in self.SUPPORTED_LANGUAGES:
            lang_file = self.locales_dir / f"{lang}.json"
            if lang_file.exists():
                with open(lang_file, "r", encoding="utf-8") as f:
                    self._translations[lang] = json.load(f)
            else:
                print(f"Warning: Translation file not found: {lang_file}")
                self._translations[lang] = {}

    @property
    def language(self) -> str:
        """Get current language.

        Returns:
            Current language code.
        """
        return self._config.get("language", self.DEFAULT_LANGUAGE)

    @language.setter
    def language(self, value: str) -> None:
        """Set current language.

        Args:
            value: Language code to set.

        Raises:
            ValueError: If language is not supported.
        """
        if value not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language: {value}. "
                f"Supported: {', '.join(self.SUPPORTED_LANGUAGES)}"
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
            translations = self._translations.get(self.DEFAULT_LANGUAGE, {})

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
            List of language codes.
        """
        return self.SUPPORTED_LANGUAGES.copy()
