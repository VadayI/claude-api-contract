import "@typespec/http";
import "@typespec/openapi";
import "./models/errors.tsp";

using Http;
using OpenAPI;

namespace ClaudeApiContract;

// ---------------------------------------------------------------------------
// Auth models (user-flow D1 + service-flow D5).
// ---------------------------------------------------------------------------

/** A registered user account. */
@doc("A registered user account.")
model User {
  @doc("Unique user identifier.")
  id: string;

  @doc("User email address.")
  @extension("x-faker", "internet.email")
  email: string;

  @doc("Optional display name.")
  @extension("x-faker", "name.fullName")
  name?: string;
}

/** Access + refresh token pair (refresh is returned in the body, D2). */
@doc("Access + refresh token pair.")
model TokenPair {
  @doc("Short-lived JWT access token.")
  access: string;

  @doc("Long-lived refresh token (returned in the response body).")
  refresh: string;
}

/** Credentials to register a new user account. */
@doc("Credentials to register a new user account.")
model RegisterRequest {
  @doc("User email address.")
  email: string;

  @doc("Plain-text password (transport-encrypted).")
  password: string;

  @doc("Optional display name.")
  name?: string;
}

/** Result of registering a user. */
@doc("Result of registering a user (user plus an optional initial token pair).")
model RegisterResponse {
  @doc("The newly created user.")
  user: User;

  @doc("Optional initial access + refresh token pair.")
  tokens?: TokenPair;
}

/** Login credentials. */
@doc("Login credentials.")
model LoginRequest {
  @doc("User email address.")
  email: string;

  @doc("Plain-text password (transport-encrypted).")
  password: string;
}

/** Refresh token request body (also used to revoke on logout). */
@doc("Refresh token request body.")
model RefreshRequest {
  @doc("The refresh token previously issued.")
  refresh: string;
}

/** A renewed access token, optionally with a rotated refresh token. */
@doc("A renewed access token, optionally with a rotated refresh token.")
model AccessToken {
  @doc("Short-lived JWT access token.")
  access: string;

  @doc("Rotated refresh token, if refresh rotation is enabled.")
  refresh?: string;
}

/** Service-to-service client-credentials token request (JSON body, D5). */
@doc("Service-to-service client-credentials token request.")
model ServiceTokenRequest {
  @doc("OAuth2 grant type; must be 'client_credentials'.")
  grant_type: string;

  @doc("Service client identifier.")
  client_id: string;

  @doc("Service client secret.")
  client_secret: string;

  @doc("Optional space-separated list of requested scopes.")
  scope?: string;
}

/** Service-to-service access token response. */
@doc("Service-to-service access token response.")
model ServiceTokenResponse {
  @doc("Short-lived JWT access token.")
  access: string;

  @doc("Token type; always 'Bearer'.")
  token_type: string;

  @doc("Token lifetime in seconds.")
  expires_in: int32;

  @doc("Granted scopes (space-separated).")
  scope: string;
}

// ---------------------------------------------------------------------------
// Auth operations.
// ---------------------------------------------------------------------------

@tag("auth")
@route("/api/v1/auth/register")
@post
@summary("Register a new user")
@doc("Create a new user account. Public endpoint.")
@useAuth(NoAuth)
@opExample(#{
  parameters: #{
    body: #{
      email: "ada@example.com",
      password: "S3cure-pass!",
      name: "Ada Lovelace",
    },
  },
  returnType: #{
    statusCode: 201,
    body: #{
      user: #{
        id: "usr_01HZX3K9P2",
        email: "ada@example.com",
        name: "Ada Lovelace",
      },
      tokens: #{
        access: "eyJhbGciOiJIUzI1NiJ9.reg-access",
        refresh: "r3fr3sh-tok3n-reg",
      },
    },
  },
})
@opExample(#{
  returnType: #{
    statusCode: 400,
    body: #{
      errors: #[
        #{
          field: "email",
          code: "invalid",
          message: "Enter a valid email address.",
        }
      ],
    },
  },
})
@opExample(#{
  returnType: #{
    statusCode: 409,
    body: #{ detail: "A user with this email already exists." },
  },
})
op registerUser(
  @doc("Registration credentials.")
  @body
  body: RegisterRequest,
):
  | {
      @statusCode statusCode: 201;

      @doc("The created user and optional initial tokens.")
      @body
      body: RegisterResponse;
    }
  | ValidationError
  | ConflictError;

@tag("auth")
@route("/api/v1/auth/login")
@post
@summary("Log in")
@doc("Exchange user credentials for an access + refresh token pair. Public endpoint.")
@useAuth(NoAuth)
@opExample(#{
  parameters: #{
    body: #{ email: "ada@example.com", password: "S3cure-pass!" },
  },
  returnType: #{
    access: "eyJhbGciOiJIUzI1NiJ9.access",
    refresh: "r3fr3sh-tok3n-login",
  },
})
@opExample(#{
  returnType: #{
    statusCode: 400,
    body: #{
      errors: #[
        #{
          field: "email",
          code: "invalid",
          message: "Enter a valid email address.",
        }
      ],
    },
  },
})
@opExample(#{
  returnType: #{
    statusCode: 401,
    body: #{
      detail: "Authentication credentials were not provided or are invalid.",
    },
  },
})
op loginUser(
  @doc("Login credentials.")
  @body
  body: LoginRequest,
): TokenPair | ValidationError | UnauthorizedError;

@tag("auth")
@route("/api/v1/auth/refresh")
@post
@summary("Refresh the access token")
@doc("Exchange a valid refresh token for a new access token. Public endpoint.")
@useAuth(NoAuth)
@opExample(#{
  parameters: #{ body: #{ refresh: "r3fr3sh-tok3n-login" } },
  returnType: #{
    access: "eyJhbGciOiJIUzI1NiJ9.access-new",
    refresh: "r3fr3sh-rotated-tok3n",
  },
})
@opExample(#{
  returnType: #{
    statusCode: 401,
    body: #{
      detail: "Authentication credentials were not provided or are invalid.",
    },
  },
})
op refreshToken(
  @doc("The refresh token to exchange.")
  @body
  body: RefreshRequest,
): AccessToken | ValidationError | UnauthorizedError;

@tag("auth")
@route("/api/v1/auth/logout")
@post
@summary("Log out")
@doc("Invalidate the current session; optionally revoke the supplied refresh token.")
@useAuth(BearerAuth)
@opExample(#{ parameters: #{ body: #{ refresh: "r3fr3sh-tok3n-login" } } })
op logoutUser(
  @doc("Optional refresh token to revoke.")
  @body
  body?: RefreshRequest,
):
  | {
      @statusCode statusCode: 204;
    }
  | UnauthorizedError;

@tag("auth")
@route("/api/v1/auth/token")
@post
@summary("Issue a service token")
@doc("Service-to-service client-credentials grant. Returns a scoped access token. Public endpoint.")
@useAuth(NoAuth)
@opExample(#{
  parameters: #{
    body: #{
      grant_type: "client_credentials",
      client_id: "svc_articles_sync",
      client_secret: "cs_7f3a9b2e1d6c4805a1f2",
      scope: "articles:read articles:write",
    },
  },
  returnType: #{
    access: "eyJhbGciOiJIUzI1NiJ9.svc-access",
    token_type: "Bearer",
    expires_in: 900,
    scope: "articles:read articles:write",
  },
})
@opExample(#{
  returnType: #{
    statusCode: 401,
    body: #{
      detail: "Authentication credentials were not provided or are invalid.",
    },
  },
})
op issueServiceToken(
  @doc("Client-credentials token request.")
  @body
  body: ServiceTokenRequest,
): ServiceTokenResponse | ValidationError | UnauthorizedError;
