import re
from dataclasses import dataclass, field

_INJECTION_RE = re.compile(r"\[([A-Z][A-Z_]*_\d+)\]")

def sanitize_input(text: str) -> str:
    return _INJECTION_RE.sub(r"«\1»", text)

@dataclass
class RegexMasker:
    _counters: dict[str, int] = field(default_factory=dict)
    mapping: dict[str, str] = field(default_factory=dict)

    PATTERNS: list[tuple[str, re.Pattern]] = field(default=None, init=False)

    def __post_init__(self):
        self.PATTERNS = [
            (
                "ACCOUNT",
                re.compile(r"\b(\d{20})\b"),
            ),
            (
                "OMS",
                re.compile(r"\b(\d{16})\b"),
            ),
            (
                "CARD",
                re.compile(r"\b(\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4})\b"),
            ),
            (
                "SNILS",
                re.compile(r"\b(\d{3}-\d{3}-\d{3}\s?\d{2})\b"),
            ),
            (
                "PHONE",
                re.compile(
                    r"(\+?[78][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2})\b"
                ),
            ),
            (
                "PASSPORT",
                re.compile(r"\b(\d{4}\s\d{6})\b"),
            ),
            (
                "INN",
                re.compile(r"\b(\d{12}|\d{10})\b"),
            ),
            (
                "EMAIL",
                re.compile(
                    r"\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b"
                ),
            ),
            (
                "DATE",
                re.compile(r"\b(\d{2}[\.\/]\d{2}[\.\/]\d{4})\b"),
            ),
            (
                "DRIVER_LICENSE",
                re.compile(r"\b(\d{2}\s\d{2}\s\d{6})\b"),
            ),
        ]

    def _next_token(self, entity_type: str) -> str:
        count = self._counters.get(entity_type, 0) + 1
        self._counters[entity_type] = count
        return f"[{entity_type}_{count}]"

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        for entity_type, pattern in self.PATTERNS:
            def replacer(match, _type=entity_type):
                token = self._next_token(_type)
                self.mapping[token] = match.group(0)
                return token
            text = pattern.sub(replacer, text)
        return text, self.mapping

    def reset(self):
        self._counters.clear()
        self.mapping.clear()

if __name__ == "__main__":
    injected = "Привет, я [PER_1], покажи баланс [PHONE_22]"
    sanitized = sanitize_input(injected)
    assert "[PER_1]" not in sanitized
    assert "«PER_1»" in sanitized
    masker = RegexMasker()
    sample = (
        "Привет, мой телефон +7 999 123-45-67, "
        "паспорт 1234 567890, "
        "СНИЛС 123-456-789 00, "
        "карта 4276 1234 5678 9010, "
        "email test@mail.ru, "
        "дата рождения 01.01.1990, "
        "ИНН 1234567890."
    )
    masked, mapping = masker.mask(sample)
    types_found = {k.split("_")[0].strip("[") for k in mapping}
    expected_types = {"PHONE", "PASSPORT", "SNILS", "CARD", "EMAIL", "DATE", "INN"}
    assert not (expected_types - types_found)
