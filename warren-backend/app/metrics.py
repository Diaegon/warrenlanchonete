"""Prometheus custom metrics for Warren Lanchonete backend.

These metrics are registered once at module import time and reused throughout
the application lifecycle. Import this module in services to increment/observe.

Metrics:
    openai_calls_total: Counter of OpenAI API calls by call_type.
    openai_duration_seconds: Histogram of OpenAI call duration by call_type.
    rag_results_count: Histogram of RAG retrieval result counts per query.
"""

from prometheus_client import Counter, Histogram

openai_calls_total = Counter(
    "warren_openai_calls_total",
    "Total number of OpenAI API calls made by Warren Lanchonete",
    ["call_type"],  # Labels: "per_stock" or "summary"
)

openai_duration_seconds = Histogram(
    "warren_openai_duration_seconds",
    "Duration of OpenAI API calls in seconds",
    ["call_type"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 45.0, 60.0),
)

rag_results_count = Histogram(
    "warren_rag_results_total",
    "Number of RAG results returned per retrieval query",
    buckets=(1, 2, 3, 5, 10),
)
