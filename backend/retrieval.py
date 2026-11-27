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
    level: str | None = None  # the file's Level line, e.g. Undergraduate


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
                level=_header(raw, "Level"),
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


# --- Fixed lists for the Housing and Clubs tabs: parsed from the files, no model ---

# "## " headings in the associations list that are not topic areas.
NOT_AREAS = {"Tips for exchange students"}
_URL_IN_TEXT = re.compile(r"https?://[^\s()<>]+")


def _read(path: Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return None


def _source(path: Path, raw: str) -> dict:
    return {"file": _relative(Path(path)), "title": _header(raw, "Topic") or Path(path).stem, "url": _header(raw, "Source")}


def _sections(raw: str) -> dict[str, str]:
    """Body under each '## ' heading, keyed by heading, in file order."""
    parts = re.split(r"^## +(.+?)\s*$", raw, flags=re.MULTILINE)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _bullets(text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"^- +(.+?)\s*$", text, re.MULTILINE)]


def housing_websites(path: Path) -> dict:
    """Websites from the '## Websites' section, as [{name, url}] in file order."""
    raw = _read(path)
    if raw is None:
        return {"websites": [], "source": None}
    websites = []
    for bullet in _bullets(_sections(raw).get("Websites", "")):
        match = re.match(r"(.+?)\s+[–-]\s+(https?://\S+?)(?:\s+[–-]\s+.*)?$", bullet)
        if match:
            websites.append({"name": match.group(1), "url": match.group(2)})
    return {"websites": websites, "source": _source(path, raw)}


def club_areas(path: Path) -> dict:
    """Topic areas ('## ' headings, except NOT_AREAS) with their clubs, in file order."""
    raw = _read(path)
    if raw is None:
        return {"areas": [], "source": None}
    areas = [
        {"name": name, "clubs": _bullets(body)}
        for name, body in _sections(raw).items()
        if name not in NOT_AREAS and _bullets(body)
    ]
    return {"areas": areas, "source": _source(path, raw)}


def _line_value(text: str, key: str) -> str | None:
    match = re.search(rf"^- +{key}:\s*(.+?)\s*$", text, re.MULTILINE)
    return match.group(1) if match else None


def _esn(path: Path) -> dict | None:
    raw = _read(path)
    if raw is None:
        return None
    for name, body in _sections(raw).items():
        if not name.startswith("ESN"):
            continue
        website = _URL_IN_TEXT.search(_line_value(body, "Website") or "")
        handle = re.match(r"@([A-Za-z0-9_.]+)", _line_value(body, "Instagram") or "")
        return {
            "name": name,
            "website": website.group(0) if website else None,
            # The file gives only the handle; the profile URL is built from it here, in code.
            "instagram": {"handle": handle.group(0), "url": f"https://www.instagram.com/{handle.group(1)}"}
            if handle
            else None,
            "app": _line_value(body, "App"),
            "source": _source(path, raw),
        }
    return None


def _fair(path: Path) -> dict | None:
    raw = _read(path)
    if raw is None:
        return None
    for bullet in _bullets(raw):
        if "Associations on Display" in bullet:
            event = _URL_IN_TEXT.search(bullet)
            text = re.sub(r"\s*\(source:\s*https?://[^)]+\)", "", bullet)
            return {"text": text, "event_url": event.group(0) if event else None, "source": _source(path, raw)}
    return None


def start_here(community_path: Path, join_path: Path) -> dict:
    """ESN card (website, Instagram, app) and the Associations on Display fair, taken from the files."""
    return {"esn": _esn(community_path), "fair": _fair(join_path)}
