# Orbit Search: operations and security

This guide organizes runtime behavior documented by the package. It does not certify production readiness. Verify provider/client versions, permissions, transport security, limits, and failure behavior in the target environment before release.

## Configuration surface

Environment names found in the package README:

The package README does not name `ORBIT_*` variables. Use its typed constructors and application configuration, and confirm exact runtime inputs in the implementation before deployment.

Use the package README's constructor and deployment examples. Store credentials in a secret manager and avoid logging credentials, raw provider errors, request data, or opaque cursors.

## Lifecycle, failure behavior, and limits

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

## Production validation

Validate startup/shutdown cleanup, timeout and cancellation behavior, concurrency and payload bounds where applicable, secret rotation and least-privilege access, data durability, backup/restore, and failover against the selected provider. Do not infer distributed or durable guarantees from an in-process API or fake-client tests.
