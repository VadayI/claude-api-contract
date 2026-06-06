import "@typespec/http";

using Http;

namespace ClaudeApiContract;

/** Simple error envelope used by 401/403/404/409/429/500 responses. */
@doc("Simple error envelope with a single human-readable message.")
model ErrorDetail {
  @doc("Human-readable error message.")
  detail: string;
}

/** A single field-level validation error. */
@doc("A single field-level validation error.")
model FieldError {
  @doc("Name of the field that failed validation.")
  field: string;

  @doc("Stable, machine-readable error code (e.g. 'required', 'invalid').")
  code: string;

  @doc("Human-readable explanation of the validation failure.")
  message: string;
}

/** Validation error envelope used by 400 responses. */
@doc("Validation error envelope carrying a list of per-field errors.")
model ValidationErrors {
  @doc("List of per-field validation errors.")
  errors: FieldError[];
}

/** 400 — request body failed validation. */
@error
model ValidationError {
  @statusCode statusCode: 400;

  @doc("Validation error payload.")
  @body
  body: ValidationErrors;
}

/** 401 — authentication is missing or invalid. */
@error
model UnauthorizedError {
  @statusCode statusCode: 401;

  @doc("Error payload.")
  @body
  body: ErrorDetail;
}

/** 403 — authenticated but not permitted (missing scope/permission). */
@error
model ForbiddenError {
  @statusCode statusCode: 403;

  @doc("Error payload.")
  @body
  body: ErrorDetail;
}

/** 404 — the requested resource does not exist. */
@error
model NotFoundError {
  @statusCode statusCode: 404;

  @doc("Error payload.")
  @body
  body: ErrorDetail;
}

/** 409 — the request conflicts with the current state of the resource. */
@error
model ConflictError {
  @statusCode statusCode: 409;

  @doc("Error payload.")
  @body
  body: ErrorDetail;
}

/** 429 — rate limit exceeded; retry after the indicated delay. */
@error
model RateLimitError {
  @statusCode statusCode: 429;

  @doc("Seconds to wait before retrying.")
  @header("Retry-After")
  retryAfter: int32;

  @doc("Error payload.")
  @body
  body: ErrorDetail;
}
