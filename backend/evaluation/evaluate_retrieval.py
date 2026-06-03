"""Lightweight RAG retrieval and optional answer evaluation.

Run from the backend directory:
    python evaluation/evaluate_retrieval.py --eval-file evaluation/sample_eval_set.json --top-k 10

Optional answer mode may use configured LLM quota:
    python evaluation/evaluate_retrieval.py --eval-file evaluation/sample_eval_set.json --with-answer
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.agent.controller import run_agent
from app.core.retrieval.bm25_store import get_bm25_store
from app.core.retrieval.hybrid import RetrievalResult, get_hybrid_retriever
from app.db.session import async_session_factory
from app.models.db_models import Document


@dataclass
class EvalItem:
    id: str
    question: str
    expected_keywords: list[str]
    expected_file: str | None = None
    expected_pages: list[int] | None = None
    notes: str | None = None


@dataclass
class LocalDocument:
    document_id: str
    file_name: str
    status: str
    total_chunks: int


def load_eval_set(path: Path) -> list[EvalItem]:
    with path.open("r", encoding="utf-8") as handle:
        raw_items = json.load(handle)

    if not isinstance(raw_items, list):
        raise ValueError("Evaluation file must contain a JSON array.")

    items: list[EvalItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        if not raw.get("id") or not raw.get("question"):
            raise ValueError("Each eval item must include at least 'id' and 'question'.")
        items.append(
            EvalItem(
                id=str(raw["id"]),
                question=str(raw["question"]),
                expected_keywords=[str(value) for value in raw.get("expected_keywords", [])],
                expected_file=raw.get("expected_file"),
                expected_pages=raw.get("expected_pages") or [],
                notes=raw.get("notes"),
            )
        )
    return items


async def load_document_names() -> dict[str, str]:
    async with async_session_factory() as db:
        result = await db.execute(select(Document.id, Document.file_name))
        return {document_id: file_name for document_id, file_name in result.all()}


async def load_local_documents() -> list[LocalDocument]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Document.id, Document.file_name, Document.status, Document.total_chunks)
            .order_by(Document.upload_time.desc())
        )
        return [
            LocalDocument(
                document_id=document_id,
                file_name=file_name,
                status=status,
                total_chunks=int(total_chunks or 0),
            )
            for document_id, file_name, status, total_chunks in result.all()
        ]


async def print_local_documents() -> None:
    try:
        documents = await load_local_documents()
    except Exception as error:
        print(f"Unable to read local documents from SQLite: {error}")
        return

    if not documents:
        print("No documents found. Upload documents first.")
        return

    print("Local documents")
    for document in documents:
        print(f"- file_name: {document.file_name}")
        print(f"  status: {document.status}")
        print(f"  total_chunks: {document.total_chunks}")
        print(f"  document_id: {document.document_id}")


def normalize(value: str | None) -> str:
    return (value or "").casefold().strip()


def keyword_overlap(expected_keywords: list[str], text: str) -> dict[str, Any]:
    if not expected_keywords:
        return {
            "score": None,
            "matched": [],
            "missing": [],
        }

    text_normalized = normalize(text)
    matched = [
        keyword
        for keyword in expected_keywords
        if normalize(keyword) in text_normalized
    ]
    missing = [keyword for keyword in expected_keywords if keyword not in matched]
    return {
        "score": len(matched) / len(expected_keywords),
        "matched": matched,
        "missing": missing,
    }


async def create_template(path: Path, force: bool = False) -> None:
    if not path.is_absolute():
        path = BACKEND_ROOT / path

    if path.exists() and not force:
        print(f"Template already exists: {path}")
        print("Pass --force to overwrite it.")
        return

    try:
        documents = await load_local_documents()
    except Exception as error:
        print(f"Unable to read local documents from SQLite: {error}")
        return

    if not documents:
        print("No documents found. Upload documents first.")
        return

    template_items = [
        {
            "id": f"eval_{index:03d}",
            "question": "Write your question here about this document.",
            "expected_keywords": [],
            "expected_file": document.file_name,
            "expected_pages": [],
            "notes": "Replace this with a meaningful expected source note.",
        }
        for index, document in enumerate(documents, 1)
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(template_items, handle, indent=2, ensure_ascii=False)

    print(f"Created eval template: {path}")
    print(f"Included {len(template_items)} document(s). Edit questions, keywords, and expected pages before scoring.")


def retrieval_to_dict(result: RetrievalResult, file_name: str) -> dict[str, Any]:
    return {
        "chunk_id": result.chunk_id,
        "document_id": result.document_id,
        "file_name": file_name,
        "page_number": result.page_number,
        "section_title": result.section_title,
        "chunk_index": result.chunk_index,
        "sources": result.sources,
        "rrf_score": result.rrf_score,
        "vector_score": result.vector_score,
        "bm25_score": result.bm25_score,
        "snippet": " ".join(result.content.split())[:300],
    }


def best_score(result: RetrievalResult) -> float:
    scores = [
        score
        for score in (result.rrf_score, result.vector_score, result.bm25_score)
        if score is not None
    ]
    return max(scores) if scores else 0.0


def preview_text(text: str, max_length: int = 180) -> str:
    preview = " ".join(text.split())
    return preview if len(preview) <= max_length else f"{preview[:max_length].rstrip()}..."


def print_retrieved_chunks(
    retrieved: list[RetrievalResult],
    file_names: dict[str, str],
) -> None:
    if not retrieved:
        print("  top results: none")
        return

    print("  top results:")
    for rank, result in enumerate(retrieved, 1):
        file_name = file_names.get(result.document_id, "unknown")
        page = result.page_number if result.page_number is not None else "-"
        sources = ", ".join(result.sources or []) or "-"
        print(f"    {rank}. {file_name} | page={page} | chunk_id={result.chunk_id}")
        print(f"       score={best_score(result):.6f} | sources={sources}")
        print(f"       {preview_text(result.content)}")


def source_distribution(retrieved: list[RetrievalResult]) -> dict[str, int]:
    distribution = {
        "bm25": 0,
        "vector": 0,
        "graph": 0,
        "unknown": 0,
    }

    for result in retrieved:
        sources = {source.lower() for source in (result.sources or [])}
        recognized = False

        if "bm25" in sources:
            distribution["bm25"] += 1
            recognized = True
        if "vector" in sources:
            distribution["vector"] += 1
            recognized = True
        if "graph" in sources or "neo4j" in sources:
            distribution["graph"] += 1
            recognized = True
        if not recognized:
            distribution["unknown"] += 1

    return distribution


def vector_absence_warning(retrieved: list[RetrievalResult]) -> str | None:
    if not retrieved:
        return None

    all_bm25_only = all(
        {source.lower() for source in (result.sources or [])} == {"bm25"}
        for result in retrieved
    )
    vector_score_missing = all(result.vector_score is None for result in retrieved)

    if all_bm25_only or vector_score_missing:
        return (
            "Vector retrieval did not appear in the top-k results. "
            "Check Qdrant indexing or hybrid fusion settings."
        )
    return None


def score_retrieval(
    item: EvalItem,
    retrieved: list[RetrievalResult],
    file_names: dict[str, str],
) -> dict[str, Any]:
    expected_file = normalize(item.expected_file)
    expected_pages = set(item.expected_pages or [])
    retrieved_files = [file_names.get(result.document_id, "unknown") for result in retrieved]
    retrieved_pages = [result.page_number for result in retrieved]
    top1_file = retrieved_files[0] if retrieved_files else None
    top1_page = retrieved_pages[0] if retrieved_pages else None

    file_hit = None
    hit_at_1 = None
    hit_at_3 = None
    hit_at_5 = None
    first_relevant_rank = None
    mrr_contribution = None
    top1_is_expected_file = None
    if expected_file:
        relevant_ranks = [
            rank
            for rank, file_name in enumerate(retrieved_files, 1)
            if normalize(file_name) == expected_file
        ]
        first_relevant_rank = relevant_ranks[0] if relevant_ranks else None
        file_hit = first_relevant_rank is not None
        hit_at_1 = bool(first_relevant_rank and first_relevant_rank <= 1)
        hit_at_3 = bool(first_relevant_rank and first_relevant_rank <= 3)
        hit_at_5 = bool(first_relevant_rank and first_relevant_rank <= 5)
        mrr_contribution = 1 / first_relevant_rank if first_relevant_rank else 0
        top1_is_expected_file = normalize(top1_file) == expected_file if top1_file else False

    page_hit = None
    if expected_pages:
        page_hit = any(page in expected_pages for page in retrieved_pages if page is not None)

    combined_context = "\n\n".join(result.content for result in retrieved)
    overlap = keyword_overlap(item.expected_keywords, combined_context)

    return {
        "hit_at_1": hit_at_1,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "hit_at_k": file_hit,
        "first_relevant_rank": first_relevant_rank,
        "mrr_contribution": mrr_contribution,
        "top1_file": top1_file,
        "top1_page": top1_page,
        "top1_is_expected_file": top1_is_expected_file,
        "page_hit_at_k": page_hit,
        "keyword_overlap": overlap,
        "retrieved_count": len(retrieved),
        "top_files": retrieved_files,
        "top_pages": retrieved_pages,
        "source_distribution": source_distribution(retrieved),
    }


async def evaluate_answer(
    item: EvalItem,
    file_names: dict[str, str],
) -> dict[str, Any]:
    async with async_session_factory() as db:
        response = await run_agent(item.question, document_ids=None, db=db)

    citations = response.citations or []
    answer_overlap = keyword_overlap(item.expected_keywords, response.answer)
    expected_file = normalize(item.expected_file)
    citation_files = [citation.file_name for citation in citations]
    expected_file_in_citations = None
    if expected_file:
        expected_file_in_citations = any(
            normalize(file_name) == expected_file for file_name in citation_files
        )

    return {
        "answer_length": len(response.answer),
        "citation_count": len(citations),
        "expected_keywords_in_answer": answer_overlap,
        "expected_file_in_citations": expected_file_in_citations,
        "citation_files": citation_files,
        "citations": [
            citation.model_dump() if hasattr(citation, "model_dump") else dict(citation)
            for citation in citations
        ],
        "known_document_count": len(file_names),
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    def average_bool(metric: str) -> float | None:
        values = [
            result["retrieval"][metric]
            for result in results
            if result["retrieval"][metric] is not None
        ]
        return sum(1 for value in values if value) / len(values) if values else None

    scored_page_hits = [
        result["retrieval"]["page_hit_at_k"]
        for result in results
        if result["retrieval"]["page_hit_at_k"] is not None
    ]
    mrr_scores = [
        result["retrieval"]["mrr_contribution"]
        for result in results
        if result["retrieval"]["mrr_contribution"] is not None
    ]
    keyword_scores = [
        result["retrieval"]["keyword_overlap"]["score"]
        for result in results
        if result["retrieval"]["keyword_overlap"]["score"] is not None
    ]
    retrieved_counts = [result["retrieval"]["retrieved_count"] for result in results]
    aggregate_sources = {
        "bm25": 0,
        "vector": 0,
        "graph": 0,
        "unknown": 0,
    }
    for result in results:
        for source, count in result["retrieval"]["source_distribution"].items():
            aggregate_sources[source] = aggregate_sources.get(source, 0) + count

    return {
        "items": len(results),
        "hit_at_1": average_bool("hit_at_1"),
        "hit_at_3": average_bool("hit_at_3"),
        "hit_at_5": average_bool("hit_at_5"),
        "hit_at_k": average_bool("hit_at_k"),
        "mrr": sum(mrr_scores) / len(mrr_scores) if mrr_scores else None,
        "page_hit_at_k": (
            sum(1 for value in scored_page_hits if value) / len(scored_page_hits)
            if scored_page_hits else None
        ),
        "keyword_overlap_avg": (
            sum(keyword_scores) / len(keyword_scores) if keyword_scores else None
        ),
        "average_chunks_returned": (
            sum(retrieved_counts) / len(retrieved_counts) if retrieved_counts else 0
        ),
        "source_distribution": aggregate_sources,
    }


def print_item_result(item: EvalItem, result: dict[str, Any]) -> None:
    retrieval = result["retrieval"]
    print(f"\n[{item.id}] {item.question}")
    print(f"  retrieved: {retrieval['retrieved_count']} chunks")
    print(f"  hit@1: {retrieval['hit_at_1']}")
    print(f"  hit@3: {retrieval['hit_at_3']}")
    print(f"  hit@5: {retrieval['hit_at_5']}")
    print(f"  hit@k: {retrieval['hit_at_k']}")
    print(f"  first_relevant_rank: {retrieval['first_relevant_rank']}")
    print(f"  mrr_contribution: {retrieval['mrr_contribution']}")
    print(f"  top1: file={retrieval['top1_file']} page={retrieval['top1_page']}")
    print(f"  top1_is_expected_file: {retrieval['top1_is_expected_file']}")
    print(f"  source_distribution: {retrieval['source_distribution']}")
    print(f"  page_hit@k: {retrieval['page_hit_at_k']}")
    overlap = retrieval["keyword_overlap"]
    print(f"  keyword_overlap: {overlap['score']} matched={overlap['matched']}")
    if result.get("warnings"):
        for warning in result["warnings"]:
            print(f"  warning: {warning}")
    if result.get("answer"):
        answer = result["answer"]
        print(f"  answer_length: {answer.get('answer_length')}")
        print(f"  citation_count: {answer.get('citation_count')}")


def missing_expected_file_warning(expected_file: str, available_file_names: list[str]) -> str:
    available = ", ".join(available_file_names) if available_file_names else "none"
    return (
        f"Expected file not found.\n"
        f"    expected_file: {expected_file}\n"
        f"    available local file names: {available}\n"
        "    suggestion: Run --list-documents and update expected_file to match the exact uploaded file name."
    )


async def run_evaluation(args: argparse.Namespace) -> dict[str, Any]:
    eval_file = Path(args.eval_file)
    if not eval_file.is_absolute():
        eval_file = BACKEND_ROOT / eval_file

    items = load_eval_set(eval_file)
    print(f"Loaded {len(items)} eval item(s) from {eval_file}")

    try:
        await get_bm25_store().initialize_from_db()
    except Exception as error:
        print(f"Warning: BM25 initialization failed: {error}")

    try:
        file_names = await load_document_names()
    except Exception as error:
        print(f"Warning: unable to load document names from DB: {error}")
        file_names = {}

    retriever = get_hybrid_retriever()
    results: list[dict[str, Any]] = []
    available_file_names = sorted(file_names.values())

    for item in items:
        warnings: list[str] = []
        if item.expected_file and item.expected_file not in file_names.values():
            warnings.append(
                missing_expected_file_warning(item.expected_file, available_file_names)
            )

        try:
            retrieved = await retriever.search(item.question, top_k=args.top_k)
        except Exception as error:
            print(f"Retrieval failed for {item.id}: {error}")
            retrieved = []
            warnings.append(f"Retrieval failed: {error}")

        vector_warning = vector_absence_warning(retrieved)
        if vector_warning:
            warnings.append(vector_warning)

        item_result: dict[str, Any] = {
            "item": asdict(item),
            "warnings": warnings,
            "retrieval": score_retrieval(item, retrieved, file_names),
            "top_chunks": [
                retrieval_to_dict(result, file_names.get(result.document_id, "unknown"))
                for result in retrieved
            ],
        }

        if args.with_answer:
            try:
                item_result["answer"] = await evaluate_answer(item, file_names)
            except Exception as error:
                item_result["answer_error"] = str(error)
                print(f"Answer evaluation failed for {item.id}: {error}")

        print_item_result(item, item_result)
        if args.show_results:
            print_retrieved_chunks(retrieved, file_names)
        results.append(item_result)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "eval_file": str(eval_file),
        "top_k": args.top_k,
        "with_answer": args.with_answer,
        "summary": summarize(results),
        "results": results,
    }

    reports_dir = BACKEND_ROOT / "evaluation" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"retrieval_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print("\nSummary")
    print(json.dumps(report["summary"], indent=2))
    print(f"\nReport saved to: {report_path}")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate Agentic StudyMate retrieval quality.")
    parser.add_argument(
        "--list-documents",
        action="store_true",
        help="Print local SQLite documents and exit.",
    )
    parser.add_argument(
        "--create-template",
        help="Create a starter eval JSON using actual local document file names.",
    )
    parser.add_argument(
        "--eval-file",
        default="evaluation/sample_eval_set.json",
        help="Path to evaluation JSON file, relative to backend/ unless absolute.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file when used with --create-template.",
    )
    parser.add_argument(
        "--show-results",
        action="store_true",
        help="Print top-k retrieved chunks for each eval item.",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Number of chunks to retrieve per question.")
    parser.add_argument(
        "--with-answer",
        action="store_true",
        help="Also run the agent answer pipeline. This may use configured LLM API quota.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.list_documents:
            asyncio.run(print_local_documents())
            return
        if args.create_template:
            asyncio.run(create_template(Path(args.create_template), force=args.force))
            return
        asyncio.run(run_evaluation(args))
    except KeyboardInterrupt:
        print("Evaluation interrupted.")
    except Exception as error:
        print(f"Evaluation failed: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
