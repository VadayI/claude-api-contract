import "@typespec/http";

using Http;

namespace ClaudeApiContract;

/**
 * Standard paginated list envelope, shared contract-wide.
 * Mirrors the Django REST Framework default so the backend consumer barely
 * adapts and the frontend has a stable shape for TanStack Query.
 */
@friendlyName("{name}List", T)
@doc("Standard paginated list envelope (count / next / previous / results).")
model ListResponse<T> {
  @doc("Total number of items across all pages.")
  count: int32;

  @doc("URL of the next page of results, or null on the last page.")
  next: url | null;

  @doc("URL of the previous page of results, or null on the first page.")
  previous: url | null;

  @doc("Items on the current page.")
  results: T[];
}
