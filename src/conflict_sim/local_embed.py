"""Embeddings computed on this machine, for runs that call no paid API.

The default model is multilingual (Korean included), symmetric (questions and memories need no
prefix), small (0.22 GB, downloaded once on first use) and runs on the CPU through ONNX, so the
`embed` extra brings in no torch.
"""

import threading
from collections.abc import Callable, Iterable, Sequence

from .llm import LLMError

DEFAULT_LOCAL_EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
INSTALL = "Install the local embedding extra: uv sync --extra embed"
Encoder = Callable[[list[str]], Iterable[Sequence[float]]]


def _text_embedding():
    try:
        from fastembed import TextEmbedding
    except ImportError as exc:
        raise LLMError(INSTALL) from exc
    return TextEmbedding


class LocalEmbedder:
    def __init__(self, model: str = DEFAULT_LOCAL_EMBED_MODEL, *, encoder: Encoder | None = None):
        self.model = model
        self._encoder = encoder
        self._lock = threading.Lock()  # one load, even when the first calls come from threads

    def _encode(self) -> Encoder:
        with self._lock:
            if self._encoder is None:
                kind = _text_embedding()
                try:
                    loaded = kind(self.model)
                except Exception as exc:  # download, cache or model-name failures
                    raise LLMError(
                        f"Local embedding model {self.model} could not be loaded: "
                        f"{type(exc).__name__}"
                    ) from None
                self._encoder = lambda texts: loaded.embed(texts)
            return self._encoder

    def __call__(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        encode = self._encode()
        try:  # fastembed computes lazily: errors can come while the vectors are read
            vectors = [[float(x) for x in vector] for vector in encode(list(texts))]
        except Exception as exc:  # an LLMError pauses the run (resumable); others would fail it
            raise LLMError(
                f"Local embedding model {self.model} failed: {type(exc).__name__}"
            ) from None
        if len(vectors) != len(texts):
            raise LLMError("Local embedding count does not match the input")
        return vectors
