from regex_masker import RegexMasker, sanitize_input
from ner_masker import NerMasker

class MaskingPipeline:
    def __init__(self):
        self.regex_masker = RegexMasker()
        self.ner_masker = NerMasker()

    def mask(self, text: str) -> tuple[str, dict[str, str]]:
        text = sanitize_input(text)
        text, regex_mapping = self.regex_masker.mask(text)
        text, full_mapping = self.ner_masker.mask(text, existing_mapping=regex_mapping)
        return text, full_mapping

    def reset(self):
        self.regex_masker.reset()
        self.ner_masker.reset()

if __name__ == "__main__":
    pipeline = MaskingPipeline()
    sample = (
        "Привет, я Иванов Иван Иванович, мой телефон +7 999 123-45-67, "
        "паспорт 1234 567890, СНИЛС 123-456-789 00, "
        "карта 4276 1234 5678 9010, email ivan@mail.ru. "
        "Живу в Москве, работаю в Альфа-Банке."
    )
    masked, mapping = pipeline.mask(sample)
    print("MASKED:", masked)
    print()
    print("MAPPING:")
    for token, value in mapping.items():
        print(f"  {token} → {value}")
