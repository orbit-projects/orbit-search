# Orbit Search: architecture and boundaries

## Responsibility

`orbit-search` defines a provider-neutral asynchronous search contract. It validates bounded text
queries, explicit field paths, scalar exact-match filters, opaque pagination cursors, finite result
scores, and size-limited JSON documents. It does not contain an Elasticsearch/OpenSearch client or
claim a provider integration.

Install the capability package:

```bash
python -m pip install orbit-search
```

Provider adapters implement `SearchStore` and own SDKs, credentials, configuration, transport,
resource lifecycle, and provider error mapping. They should translate the portable query fields
with parameterized provider APIs and document differences in ranking, consistency, and pagination.
No provider DSL, query syntax, automatic retry, or close method is imposed on the shared contract.

```python
from orbit_search import SearchQuery, SearchStore


async def find_articles(store: SearchStore):
    query = SearchQuery(
        text="async cancellation",
        fields=("title", "body"),
        filters={"visibility": "public"},
        page_size=25,
    )
    return await store.search("articles", query)
```

The input models reject provider query languages and bound page size to 100 and source documents to
1 MiB. Result payloads are detached and immutable; `model_dump()` returns JSON-compatible copies.
`SearchOperationError` provides a bounded public message and explicit retry hint. Adapters must not
place credentials, provider response bodies, or raw SDK exception text in those messages.

This package is pre-alpha and is not a published or stable release. It supports Python 3.11 through
3.14.

## Declared dependencies

The following dependency declarations come from the checked-in manifests. Optional groups and development dependencies are called out separately.

### `pyproject.toml`
- `pydantic>=2.10,<3`
- Optional `dev` group: `pytest>=8,<10`, `ruff>=0.8,<1`, `mypy>=1.13,<2`.

Declared dependencies do not mean that optional providers or services are bundled with this package.

## Implementation layout

Representative implementation files in this checkout:

- `src/orbit_search/__init__.py`
- `src/orbit_search/contracts.py`

## Public contract and scope

The README does not contain a separately headed architecture section. Its responsibility statement above and the public source files define the implemented scope; this guide adds no behavior beyond that description.

## Boundary rules

Keep provider SDKs, credentials, transports, and provider-specific error translation in provider adapters. Keep reusable capability contracts in the matching capability package and lifecycle orchestration in Core. Apply the relevant layer for this repository and preserve the dependency direction shown above.
