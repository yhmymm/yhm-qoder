import operator
import os
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import content_core as cc
from content_core import ContentCoreConfig, extract_content
from content_core.common import ExtractionOutput
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from loguru import logger
from typing_extensions import Annotated, TypedDict


def _clean_pdf_extraction_artifacts(text: str) -> str:
    """Clean common PDF extraction artifacts from docling output.

    Multi-column academic papers and embedded figures produce garbled text:
    - Lines of isolated single characters from diagrams/charts
    - Words concatenated without spaces (PDF extraction loses word boundaries)
    - Lines that are mostly single-character "words" from figure text
    - Numeric data dumps from charts/tables

    This post-processing removes the worst artifacts while preserving
    legitimate content. Uses wordninja to split concatenated words.
    """
    if not text:
        return text

    lines = text.split("\n")
    cleaned_lines: List[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip lines that are mostly single-character "words" (figure text)
        # e.g., "D e i c e t c S t c R h e e a m o so a n i L n i g nking"
        # e.g., "C V o a l l u u m es n Checker LLM SQL with Confidence"
        words = stripped.split()
        if len(words) >= 4:
            single_char_words = sum(1 for w in words if len(w) == 1 and w.isalpha())
            # If more than 25% of words are single letters, or there are 6+ single letters
            if single_char_words >= 6 or single_char_words / len(words) > 0.25:
                continue

        # Skip lines that are just sequences of numbers (chart data)
        # e.g., "140 120 100 80 60 40 20 0"
        if stripped and all(c.isdigit() or c.isspace() or c in ".,-" for c in stripped):
            digit_count = sum(1 for c in stripped if c.isdigit())
            if digit_count > 5:
                continue

        # Skip lines with spaced-out SQL keywords (PDF figure extraction artifact)
        # e.g., "S ELE CT Checker N ULL Checker" or "J OI N... L LM S QL"
        spaced_sql_patterns = re.findall(
            r'\b[A-Z]\s+[A-Z]\s+[A-Z]\s+[A-Z]+\b', stripped
        )
        if len(spaced_sql_patterns) >= 2:
            continue

        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # Fix missing spaces at camelCase boundaries (conservative)
    # Only fix lowercase -> uppercase transitions that indicate word boundaries
    # e.g., "frameworkPhase" -> "framework Phase"
    # Avoid splitting acronyms (SQL, LLM) or all-caps names
    result = re.sub(
        r'([a-z])([A-Z][a-z]+)',
        r'\1 \2',
        result
    )

    # Split concatenated words using wordninja (PDF extraction often loses
    # word boundaries, producing unreadable blocks like
    # "referstothetaskofconvertingnaturallanguagequeriesinto").
    # Process the text word-by-word to handle both long lowercase runs
    # (leftover from camelCase splitting) and mixed-case concatenations.
    try:
        import wordninja

        def _split_long_token(token: str) -> str:
            """Split a long alpha-only token into individual words."""
            if len(token) < 15 or not token.isalpha():
                return token
            # Skip tokens that are all uppercase (acronyms like SQL, LLM)
            if token.isupper():
                return token
            # Use wordninja to split (handles both all-lowercase and camelCase)
            parts = wordninja.split(token)
            if len(parts) <= 1:
                return token  # No split needed
            # Preserve original casing for the first word if it was capitalized
            if token[0].isupper() and parts:
                parts[0] = parts[0].capitalize()
            return " ".join(parts)

        # Process each whitespace-delimited token
        def _process_tokens(text: str) -> str:
            return re.sub(r'\b([a-zA-Z]{15,})\b',
                         lambda m: _split_long_token(m.group(1)),
                         text)

        result = _process_tokens(result)

        # Second pass: fix words concatenated after punctuation
        # e.g., "SQL.Large" -> "SQL. Large", "engineering.However" -> "engineering. However"
        result = re.sub(r'([.!?;:,])([A-Z][a-z]{2,})', r'\1 \2', result)
        # Also fix lowercase-after-punctuation
        result = re.sub(r'([.!?;:,])([a-z]{3,})', r'\1 \2', result)

        # Third pass: split any remaining long alpha sequences that weren't
        # caught by word boundaries (e.g., embedded in hyphenated text)
        def _split_remaining(text: str) -> str:
            parts = []
            for token in text.split():
                # Extract alpha-only segments from tokens with mixed content
                alpha_segments = re.findall(r'[a-zA-Z]{15,}', token)
                if alpha_segments and not token.isalpha():
                    new_token = token
                    for seg in alpha_segments:
                        if seg.isupper() or len(seg) < 15:
                            continue
                        split_seg = " ".join(wordninja.split(seg))
                        if split_seg != seg.lower():
                            new_token = new_token.replace(seg, split_seg, 1)
                    parts.append(new_token)
                else:
                    parts.append(token)
            return " ".join(parts)

        result = _split_remaining(result)
    except ImportError:
        logger.debug("wordninja not available, skipping word splitting")

    # Remove excessive blank lines (3+ consecutive -> 2)
    result = re.sub(r'\n{3,}', '\n\n', result)

    return result.strip()


from open_notebook.ai.models import Model, ModelManager
from open_notebook.domain.content_settings import ContentSettings
from open_notebook.domain.notebook import Asset, Source
from open_notebook.domain.transformation import Transformation
from open_notebook.graphs.transformation import graph as transform_graph
from open_notebook.utils.runtime_capabilities import engine_runtime_missing

# content-core >= 2.1 disables its own Loguru logging for library consumers.
# Both the API and the worker import this module before extracting anything,
# so re-enable it here to keep extraction logs in their output.
logger.enable("content_core")

# Default preferred languages for YouTube transcript selection, used when
# ContentSettings.youtube_preferred_languages is unset. content-core's own
# default is only ["en", "es", "pt"]; we keep the broader list Open Notebook has
# always intended so non-English videos still resolve a transcript.
YOUTUBE_PREFERRED_LANGUAGES = [
    "en",
    "pt",
    "es",
    "de",
    "nl",
    "en-GB",
    "fr",
    "hi",
    "ja",
    "zh-CN",
    "zh-TW",
]


class SourceState(TypedDict):
    # Input describing what to extract: url / file_path / content / delete_source.
    content_state: Dict[str, Any]
    # Result of content-core extraction (does NOT echo url/file_path back).
    extraction: ExtractionOutput
    apply_transformations: List[Transformation]
    source_id: str
    notebook_ids: List[str]
    source: Source
    transformation: Annotated[list, operator.add]
    embed: bool


class TransformationState(TypedDict):
    source: Source
    transformation: Transformation


def _usable_engine(engine: str, kind: str) -> str:
    """Return ``engine``, or "auto" when its opt-in runtime is not installed.

    The engine choice is persisted in the database; runtime availability comes
    from environment flags that are re-evaluated on every boot. A redeploy that
    drops OPEN_NOTEBOOK_ENABLE_CRAWL4AI/_DOCLING (or a failed on-demand install)
    therefore leaves a stored selection pointing at an absent runtime, and
    passing it through fails every extraction with no usable diagnostic. Falling
    back to content-core's "auto" chain keeps ingestion working, loudly.
    """
    missing_env_var = engine_runtime_missing(engine)
    if missing_env_var is None:
        return engine
    logger.warning(
        f"Configured {kind} engine '{engine}' is selected in Content Settings but "
        f"its runtime is not available in this container; falling back to 'auto'. "
        f"Set {missing_env_var}=true to enable it (see ADR-007)."
    )
    return "auto"


def _is_youtube_url(url: str) -> bool:
    """Whether ``url`` points at YouTube (by hostname, not substring)."""
    host = (urlparse(url).hostname or "").lower()
    return host in ("youtube.com", "youtu.be") or host.endswith(".youtube.com")


_YOUTUBE_NO_TRANSCRIPT_MESSAGE = (
    "Could not extract content from this YouTube video. "
    "No transcript or subtitles are available. "
    "Try configuring a Speech-to-Text model in Settings "
    "to transcribe the audio instead."
)


def _extraction_error(error: "cc.ContentCoreError", url: str) -> ValueError:
    """Turn a content-core extraction error into a user-facing permanent failure.

    content-core >= 2.2 raises typed errors instead of returning empty content.
    They are all treated as permanent (ValueError is in process_source's
    stop_on): content-core already retries transient failures internally,
    including NetworkError, and our worker's 15 attempts exist for SurrealDB
    transaction conflicts, not for re-fetching an unreachable page. A failed
    source can still be retried from the UI.

    The message is fixed per type: content-core's own text can carry proxy
    credentials, local paths or configuration details, so it only goes to the
    worker log (logged by the caller, and kept as the exception's cause).
    """

    if isinstance(error, cc.NoTranscriptFound):
        return ValueError(_YOUTUBE_NO_TRANSCRIPT_MESSAGE)
    # content-core reports a failure of both YouTube transcript paths (e.g.
    # IpBlocked) as "YouTube transcript extraction failed ..."; other
    # ExternalServiceErrors on a YouTube URL (speech-to-text provider, fetch
    # engine) get the generic message below.
    if (
        isinstance(error, cc.ExternalServiceError)
        and url
        and _is_youtube_url(url)
        and "youtube transcript" in str(error).lower()
    ):
        return ValueError(
            "YouTube blocked or failed the transcript request. If this keeps "
            "happening, set CCORE_YOUTUBE_PROXY (a residential proxy) or "
            "CCORE_YOUTUBE_COOKIES_FILE for the worker."
        )
    if isinstance(error, cc.NotFoundError):
        return ValueError(
            "The page was not found (it may have been removed or moved). Check the URL."
        )
    if isinstance(error, cc.NetworkError):
        return ValueError(
            "Could not reach this address (connection, timeout or DNS error). "
            "Check the URL and try again."
        )
    if isinstance(error, cc.InvalidInputError):
        return ValueError("This URL or input is not valid.")
    if isinstance(error, cc.UnsupportedTypeException):
        return ValueError("This file type is not supported.")
    if isinstance(error, cc.FileOperationError):
        return ValueError(
            "The file could not be read. It may be corrupted or in an "
            "unsupported format."
        )
    if isinstance(error, cc.ConfigurationError):
        return ValueError(
            "Content extraction is not configured correctly. Check the content "
            "processing engine and speech-to-text settings; the worker log has "
            "the details."
        )
    if isinstance(error, cc.ExternalServiceError):
        return ValueError("The content extraction service failed.")
    return ValueError("Could not extract content from this source.")


async def content_process(state: SourceState) -> dict:
    content_state: Dict[str, Any] = state["content_state"]

    # content-core 2.x takes engine/model overrides via ContentCoreConfig
    # (keyword-only), not inside the input dict.
    config_kwargs: Dict[str, Any] = {
        "youtube_languages": YOUTUBE_PREFERRED_LANGUAGES,
    }

    # Honor the persisted content-processing engine choices. content-core
    # accepts "auto"/"simple"/"firecrawl"/"jina"/"crawl4ai" for URLs and
    # "auto"/"docling"/"simple" for documents; falling back to "auto" keeps the
    # previous behavior when settings are unset.
    try:
        settings: ContentSettings = await ContentSettings.get_instance()  # type: ignore[assignment]
        if settings.youtube_preferred_languages:
            config_kwargs["youtube_languages"] = settings.youtube_preferred_languages
        if settings.default_content_processing_engine_url:
            config_kwargs["url_engine"] = _usable_engine(
                settings.default_content_processing_engine_url, "url"
            )
        if settings.default_content_processing_engine_doc:
            config_kwargs["document_engine"] = _usable_engine(
                settings.default_content_processing_engine_doc, "document"
            )
        if settings.docling_ocr is not None:
            config_kwargs["docling_ocr"] = settings.docling_ocr
        if settings.docling_formulas is not None:
            config_kwargs["docling_formulas"] = settings.docling_formulas
        if settings.docling_vision is not None:
            config_kwargs["docling_vision"] = settings.docling_vision
    except Exception as e:
        # Keep the server-side traceback for diagnosing DB/deserialization
        # failures while still falling back to defaults (non-fatal).
        logger.opt(exception=True).warning(
            f"Failed to load content settings, using defaults: {e}"
        )

    try:
        model_manager = ModelManager()
        defaults = await model_manager.get_defaults()
        if defaults.default_speech_to_text_model:
            stt_model = await Model.get(defaults.default_speech_to_text_model)
            if stt_model:
                config_kwargs["audio_provider"] = stt_model.provider
                config_kwargs["audio_model"] = stt_model.name
                logger.debug(
                    f"Using speech-to-text model: {stt_model.provider}/{stt_model.name}"
                )
    except Exception as e:
        logger.warning(f"Failed to retrieve speech-to-text model configuration: {e}")
        # Continue without custom audio model (content-core will use its default)

    config = ContentCoreConfig(**config_kwargs) if config_kwargs else None

    # Log the effective extraction engines so operators can confirm which engine
    # actually ran (content-core logs its own dispatch only at DEBUG). Absent
    # overrides fall back to content-core's "auto".
    if content_state.get("url"):
        target = "url"
    elif content_state.get("file_path"):
        target = "document"
    else:
        target = "content"
    logger.info(
        f"Extracting {target} via content-core "
        f"(url_engine={config_kwargs.get('url_engine', 'auto')}, "
        f"document_engine={config_kwargs.get('document_engine', 'auto')}, "
        f"docling_ocr={config_kwargs.get('docling_ocr', 'auto')}, "
        f"docling_formulas={config_kwargs.get('docling_formulas', 'auto')}, "
        f"docling_vision={config_kwargs.get('docling_vision', 'auto')})"
    )

    url = content_state.get("url") or ""
    try:
        processed = await extract_content(
            url=content_state.get("url"),
            file_path=content_state.get("file_path"),
            content=content_state.get("content"),
            config=config,
        )
    except cc.ContentCoreError as e:
        logger.warning(f"content-core extraction failed ({type(e).__name__}): {e}")
        raise _extraction_error(e, url) from e

    # Since content-core 2.2, empty content means the source was genuinely
    # empty; extraction failures raise (handled above).
    if not processed.content or not processed.content.strip():
        if url and _is_youtube_url(url):
            raise ValueError(_YOUTUBE_NO_TRANSCRIPT_MESSAGE)
        raise ValueError(
            "Could not extract any text content from this source. "
            "The content may be empty, inaccessible, or in an unsupported format."
        )

    # content-core 2.x no longer deletes the uploaded source file after
    # extraction (the delete_source flag it used to honor is gone). Preserve the
    # previous auto-delete behavior on our side.
    if content_state.get("delete_source") and content_state.get("file_path"):
        file_path = content_state["file_path"]
        try:
            os.unlink(file_path)
        except FileNotFoundError:
            logger.warning(f"File not found while trying to delete: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete source file {file_path}: {e}")

    return {"extraction": processed}


async def save_source(state: SourceState) -> dict:
    content_state = state["content_state"]
    extraction = state["extraction"]

    # Get existing source using the provided source_id
    source = await Source.get(state["source_id"])
    if not source:
        raise ValueError(f"Source with ID {state['source_id']} not found")

    # Update the source with processed content. content-core's ExtractionOutput
    # does not echo url/file_path back, so carry them from the input state.
    source.asset = Asset(
        url=content_state.get("url"), file_path=content_state.get("file_path")
    )
    source.full_text = _clean_pdf_extraction_artifacts(extraction.content)

    # Preserve user-set title; only overwrite placeholder or empty titles
    if extraction.title and (not source.title or source.title == "Processing..."):
        source.title = extraction.title

    await source.save()

    # NOTE: Notebook associations are created by the API immediately for UI responsiveness
    # No need to create them here to avoid duplicate edges

    if state["embed"]:
        if source.full_text and source.full_text.strip():
            logger.debug("Embedding content for vector search")
            await source.vectorize()
        else:
            logger.warning(
                f"Source {source.id} has no text content to embed, skipping vectorization"
            )

    return {"source": source}


def trigger_transformations(state: SourceState, config: RunnableConfig) -> List[Send]:
    if len(state["apply_transformations"]) == 0:
        return []

    to_apply = state["apply_transformations"]
    logger.debug(f"Applying transformations {to_apply}")

    return [
        Send(
            "transform_content",
            {
                "source": state["source"],
                "transformation": t,
            },
        )
        for t in to_apply
    ]


async def transform_content(state: TransformationState) -> Optional[dict]:
    source = state["source"]
    content = source.full_text
    # Whitespace-only text would hit the transformation graph's empty-content
    # guard; skip it here like empty text.
    if not content or not content.strip():
        return None
    transformation: Transformation = state["transformation"]

    logger.debug(f"Applying transformation {transformation.name}")
    # LangGraph accepts a partial state dict at runtime, but its typed
    # overloads require the full state type (langgraph typing limitation).
    result = await transform_graph.ainvoke(  # type: ignore[call-overload]
        dict(input_text=content, transformation=transformation),
        config=RunnableConfig(configurable={"model_id": transformation.model_id}),
    )
    await source.add_insight(transformation.title, result["output"])
    return {
        "transformation": [
            {
                "output": result["output"],
                "transformation_name": transformation.name,
            }
        ]
    }


# Create and compile the workflow
workflow = StateGraph(SourceState)

# Add nodes
workflow.add_node("content_process", content_process)
workflow.add_node("save_source", save_source)
workflow.add_node("transform_content", transform_content)
# Define the graph edges
workflow.add_edge(START, "content_process")
workflow.add_edge("content_process", "save_source")
workflow.add_conditional_edges(
    "save_source", trigger_transformations, ["transform_content"]
)
workflow.add_edge("transform_content", END)

# Compile the graph
source_graph = workflow.compile()
