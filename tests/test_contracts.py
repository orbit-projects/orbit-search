# Copyright 2026-present Orbit Contributors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for portable search bounds and immutable provider-neutral values."""

from __future__ import annotations

import asyncio
import math
import warnings

import pytest
from pydantic import ValidationError

from orbit_search import (
    SEARCH_STORE_DEPENDENCY_KEY,
    SearchHit,
    SearchIndexNotFound,
    SearchOperationError,
    SearchPage,
    SearchQuery,
    SearchStore,
    validate_collection_name,
)


def test_query_copies_and_freezes_filters() -> None:
    filters = {"tenant.visibility": "public"}
    query = SearchQuery(text="  safe query  ", fields=("title",), filters=filters)
    filters["tenant.visibility"] = "private"

    assert query.text == "  safe query  "
    assert query.filters["tenant.visibility"] == "public"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert query.model_dump()["filters"] == {"tenant.visibility": "public"}
    assert not caught
    with pytest.raises(TypeError):
        query.filters["tenant.visibility"] = "private"  # type: ignore[index]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"text": "\t", "fields": ("title",)},
        {"text": "query\nheader", "fields": ("title",)},
        {"text": "query", "fields": ()},
        {"text": "query", "fields": ("title;DROP",)},
        {"text": "query", "fields": ("title", "title")},
        {"text": "query", "fields": ("title",), "page_size": 101},
        {"text": "query", "fields": ("title",), "page_size": True},
        {"text": "query", "fields": ("title",), "filters": {"age": math.inf}},
        {"text": "query", "fields": ("title",), "filters": {"age": object()}},
        {"text": "query", "fields": ("title",), "cursor": "token\r\ninjected"},
    ],
)
def test_query_rejects_invalid_or_unsafe_inputs(kwargs: dict[str, object]) -> None:
    with pytest.raises((ValidationError, TypeError)):
        SearchQuery(**kwargs)  # type: ignore[arg-type]


def test_collection_name_is_portable_and_bounded() -> None:
    assert validate_collection_name("catalog-v2") == "catalog-v2"
    for invalid in ("", "../index", "a/b", "a b", "-leading", "a" * 256):
        with pytest.raises(ValueError):
            validate_collection_name(invalid)


def test_hit_detaches_recursively_freezes_source_and_dumps_json() -> None:
    source = {"title": "Orbit", "tags": ["async"], "meta": {"visible": True}}
    hit = SearchHit(id="doc-1", score=0.25, source=source)
    source["tags"].append("mutated")
    source["meta"]["visible"] = False

    assert hit.source["tags"] == ("async",)
    assert hit.source["meta"]["visible"] is True
    assert hit.model_dump()["source"] == {
        "title": "Orbit",
        "tags": ["async"],
        "meta": {"visible": True},
    }
    with pytest.raises(TypeError):
        hit.source["title"] = "rewritten"  # type: ignore[index]
    with pytest.raises(TypeError):
        hit.source["tags"][0] = "rewritten"  # type: ignore[index]


@pytest.mark.parametrize("score", [math.nan, math.inf, -math.inf])
def test_hit_rejects_non_finite_scores(score: float) -> None:
    with pytest.raises(ValidationError):
        SearchHit(id="doc", score=score, source={})


def test_hit_rejects_non_json_and_oversized_documents() -> None:
    with pytest.raises(ValidationError):
        SearchHit(id="doc", score=1.0, source={"value": object()})
    with pytest.raises(ValidationError):
        SearchHit(id="doc", score=1.0, source={"value": "x" * (1024 * 1024)})


def test_validation_errors_hide_result_payloads() -> None:
    secret = "private-search-payload"
    with pytest.raises(ValidationError) as caught:
        SearchHit(id="doc", score=1.0, source={"value": object(), "secret": secret})
    assert secret not in str(caught.value)


def test_hit_rejects_cyclic_document_without_recursing_forever() -> None:
    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(ValidationError):
        SearchHit(id="doc", score=1.0, source={"cycle": cyclic})


def test_page_bounds_result_count_and_cursor() -> None:
    hit = SearchHit(id="doc", score=1.0, source={})
    page = SearchPage(hits=(hit,), next_cursor="opaque", took_ms=0)
    assert page.hits == (hit,)
    with pytest.raises(ValidationError):
        SearchPage(hits=(hit,) * 101, took_ms=0)
    with pytest.raises(ValidationError):
        SearchPage(hits=(), next_cursor="bad\nvalue", took_ms=0)


def test_error_messages_are_bounded_and_retry_hint_is_explicit() -> None:
    error = SearchOperationError("Search backend is temporarily unavailable.", retryable=True)
    assert error.retryable is True
    assert str(SearchIndexNotFound("Collection was not found.")) == "Collection was not found."
    for invalid in ("", "bad\nmessage", "x" * 257):
        with pytest.raises(ValueError):
            SearchOperationError(invalid)


def test_search_store_is_async_and_provider_neutral() -> None:
    class FakeSearchStore:
        async def search(self, collection: str, query: SearchQuery) -> SearchPage:
            return SearchPage(
                hits=(SearchHit(id=f"{collection}:1", score=1.0, source={"text": query.text}),),
                took_ms=2,
            )

    async def run() -> None:
        store: SearchStore = FakeSearchStore()
        page = await store.search("articles", SearchQuery(text="hello", fields=("text",)))
        assert page.hits[0].id == "articles:1"

    assert SEARCH_STORE_DEPENDENCY_KEY == "orbit.search"
    asyncio.run(run())
