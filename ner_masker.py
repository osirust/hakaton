from dataclasses import dataclass, field
from natasha import (
    Doc,
    MorphVocab,
    NamesExtractor,
    NewsEmbedding,
    NewsMorphTagger,
    NewsNERTagger,
    NewsSyntaxParser,
    Segmenter,
)

_segmenter = Segmenter()
_morph_vocab = MorphVocab()
_emb = NewsEmbedding()
_morph_tagger = NewsMorphTagger(_emb)
_syntax_parser = NewsSyntaxParser(_emb)
_ner_tagger = NewsNERTagger(_emb)
_names_extractor = NamesExtractor(_morph_vocab)

@dataclass
class NerMasker:
    _counters: dict[str, int] = field(default_factory=dict)
    mapping: dict[str, str] = field(default_factory=dict)

    def _next_token(self, entity_type: str) -> str:
        count = self._counters.get(entity_type, 0) + 1
        self._counters[entity_type] = count
        return f"[{entity_type}_{count}]"

    def mask(
        self,
        text: str,
        existing_mapping: dict[str, str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        if existing_mapping:
            self.mapping.update(existing_mapping)

        doc = Doc(text)
        doc.segment(_segmenter)
        doc.tag_morph(_morph_tagger)
        doc.parse_syntax(_syntax_parser)
        doc.tag_ner(_ner_tagger)

        spans_sorted = sorted(doc.ner.spans, key=lambda s: s.start, reverse=True)

        for span in spans_sorted:
            original_value = text[span.start:span.stop]
            if original_value.startswith("[") and original_value.endswith("]"):
                continue
            token = self._next_token(span.type)
            self.mapping[token] = original_value
            text = text[:span.start] + token + text[span.stop:]

        return text, self.mapping

    def reset(self):
        self._counters.clear()
        self.mapping.clear()

if __name__ == "__main__":
    masker = NerMasker()
    sample = "Иванов Иван Иванович живёт в Москве и работает в Сбербанке."
    masked, mapping = masker.mask(sample)
    print("MASKED:", masked)
    print("MAPPING:", mapping)
