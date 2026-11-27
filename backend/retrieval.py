"""Search over data/ with citations: every result keeps its file and Source URL."""

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
# Home file prefix -> name shown in the dropdown, in dropdown order.
HOME_UNIVERSITIES = {"cbs_": "Copenhagen Business School", "wu_": "WU Vienna"}
EXCHANGE_PREFIX = "bocconi_"

STOPWORDS = set(
    "a an and are as at be by for from in into is it of on or such the their to with "
    "how its this that these those using use what which will can".split()
)


@dataclass(frozen=True)
class Document:
    file: str  # path relative to the repo root, e.g. data/courses/cbs_marketing.md
    source_url: str
    course: str
    ects: float | None
    side: str  # "home" or "exchange"
    text: str  # body after the header lines
    university: str | None = None  # the file's University line
    home_university: str | None = None  # dropdown name from HOME_UNIVERSITIES; None for exchange


@dataclass(frozen=True)
class Chunk:
    file: str
    source_url: str
    course: str
    ects: float | None
    text: str


def _header(raw: str, key: str) -> str | None:
    match = re.search(rf"^{key}:\s*(.+?)\s*$", raw, re.MULTILINE)
    return match.group(1) if match else None


def _parse_ects(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _home_university(name: str) -> str | None:
    for prefix, university in HOME_UNIVERSITIES.items():
        if name.startswith(prefix):
            return university
    return None


def _side(name: str) -> str | None:
    if _home_university(name):
        return "home"
    if name.startswith(EXCHANGE_PREFIX):
        return "exchange"
    return None


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def load_documents(directory: Path) -> list[Document]:
    """Read course files. Files without Source and Course lines (e.g. catalogues) are skipped."""
    docs = []
    for path in sorted(Path(directory).glob("*.md")):
        side = _side(path.name)
        raw = path.read_text(encoding="utf-8")
        source, course = _header(raw, "Source"), _header(raw, "Course")
        if side is None or not source or not course:
            continue
        body_start = raw.find("\n# ")
        docs.append(
            Document(
                file=_relative(path),
                source_url=source,
                course=course,
                ects=_parse_ects(_header(raw, "ECTS")),
                side=side,
                text=raw[body_start + 1 :] if body_start >= 0 else raw,
                university=_header(raw, "University"),
                home_university=_home_university(path.name),
            )
        )
    return docs


def load_info_documents(directory: Path) -> list[Document]:
    """Read housing/clubs files: every file with a Source line. The Topic line is the title (in `course`)."""
    docs = []
    for path in sorted(Path(directory).glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        source = _header(raw, "Source")
        if not source:
            continue
        body_start = raw.find("\n# ")
        docs.append(
            Document(
                file=_relative(path),
                source_url=source,
                course=_header(raw, "Topic") or path.stem,
                ects=None,
                side="info",
                text=raw[body_start + 1 :] if body_start >= 0 else raw,
                university=_header(raw, "University"),
            )
        )
    return docs


def home_courses(docs: list[Document]) -> list[str]:
    return [d.course for d in docs if d.side == "home"]


def home_courses_by_university(docs: list[Document]) -> dict[str, list[str]]:
    """Home course names per home university, in HOME_UNIVERSITIES order."""
    return {
        university: [d.course for d in docs if d.home_university == university]
        for university in HOME_UNIVERSITIES.values()
    }


def chunks_of(doc: Document) -> list[Chunk]:
    """Split a document's body at '## ' headings; each chunk starts with the course name."""
    parts = [p.strip() for p in re.split(r"^(?=## )", doc.text, flags=re.MULTILINE)]
    return [
        Chunk(doc.file, doc.source_url, doc.course, doc.ects, f"{doc.course}\n{part}")
        for part in parts
        if part
    ]


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]+", text.lower()) if len(t) > 2 and t not in STOPWORDS]


def _vector(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(tokens)
    return {t: n * idf.get(t, 0.0) for t, n in counts.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    dot = sum(v * b.get(t, 0.0) for t, v in a.items())
    norm = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return dot / norm if norm else 0.0


def search(home: Document, docs: list[Document], k: int = 3, per_file: int = 2) -> list[Chunk]:
    """TF-IDF search: the best `per_file` chunks from each of the `k` most relevant exchange files."""
    chunks = [c for d in docs if d.side == "exchange" for c in chunks_of(d)]
    return _rank(f"{home.course}\n{home.text}", chunks, k, per_file)


def search_question(question: str, docs: list[Document], k: int = 3, per_file: int = 20) -> list[Chunk]:
    """TF-IDF search of a student's question over the given documents (one section's folder).

    per_file is high on purpose: these files are short, and a question often uses other words than the
    text ("cost" vs "Prices", "football" vs "Sports"), so the model gets the 3 best files nearly whole.
    """
    chunks = [c for d in docs for c in chunks_of(d)]
    return _rank(question, chunks, k, per_file)


def _rank(query_text: str, chunks: list[Chunk], k: int, per_file: int) -> list[Chunk]:
    """The best `per_file` chunks from each of the `k` files most similar to the query."""
    if not chunks:
        return []
    chunk_tokens = [_tokens(c.text) for c in chunks]
    df = Counter(t for tokens in chunk_tokens for t in set(tokens))
    idf = {t: math.log((1 + len(chunks)) / (1 + n)) + 1 for t, n in df.items()}

    query = _vector(_tokens(query_text), idf)
    scored = sorted(
        ((_cosine(query, _vector(tokens, idf)), i) for i, tokens in enumerate(chunk_tokens)),
        key=lambda pair: (-pair[0], pair[1]),
    )

    file_order: list[str] = []
    picked: dict[str, list[Chunk]] = {}
    for _score, i in scored:
        chunk = chunks[i]
        if chunk.file not in picked:
            if len(file_order) == k:
                continue
            file_order.append(chunk.file)
            picked[chunk.file] = []
        if len(picked[chunk.file]) < per_file:
            picked[chunk.file].append(chunk)
    return [c for f in file_order for c in picked[f]]
