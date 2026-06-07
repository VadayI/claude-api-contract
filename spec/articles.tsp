import "@typespec/http";
import "@typespec/openapi";
import "./models/errors.tsp";
import "./models/pagination.tsp";
import "./models/security.tsp";

using Http;
using OpenAPI;

namespace ClaudeApiContract;

// ---------------------------------------------------------------------------
// Article models (blog-style resource).
// ---------------------------------------------------------------------------

/** Publication status of an article. */
@doc("Publication status of an article.")
enum ArticleStatus {
  draft,
  published,
  archived,
}

/** A blog-style article. */
@doc("A blog-style article.")
model Article {
  @doc("Unique article identifier.")
  id: string;

  @doc("Article title.")
  @extension("x-faker", "lorem.sentence")
  title: string;

  @doc("URL-friendly slug.")
  @extension("x-faker", "lorem.slug")
  slug: string;

  @doc("Article body content.")
  @extension("x-faker", "lorem.paragraphs")
  body: string;

  @doc("Publication status.")
  status: ArticleStatus;

  @doc("Identifier of the author.")
  author_id: string;

  @doc("Associated tag labels.")
  tags: string[];

  @doc("Creation timestamp (UTC).")
  @extension("x-faker", "date.recent")
  created_at: utcDateTime;

  @doc("Last update timestamp (UTC).")
  @extension("x-faker", "date.recent")
  updated_at: utcDateTime;
}

/** Payload to create an article. */
@doc("Payload to create an article.")
model ArticleCreate {
  @doc("Article title.")
  title: string;

  @doc("Article body content.")
  body: string;

  @doc("Optional URL-friendly slug; generated from the title if omitted.")
  slug?: string;

  @doc("Publication status; defaults to draft.")
  status?: ArticleStatus = ArticleStatus.draft;

  @doc("Associated tag labels.")
  tags?: string[] = #[];
}

/** Payload to update an article; all fields optional. */
@doc("Payload to partially update an article; all fields optional.")
model ArticleUpdate {
  @doc("Article title.")
  title?: string;

  @doc("URL-friendly slug.")
  slug?: string;

  @doc("Article body content.")
  body?: string;

  @doc("Publication status.")
  status?: ArticleStatus;

  @doc("Associated tag labels.")
  tags?: string[];
}

// ---------------------------------------------------------------------------
// Article operations. Human bearer OR service scope.
// ---------------------------------------------------------------------------

@tag("articles")
@route("/api/v1/articles")
@get
@summary("List articles")
@doc("Return a paginated list of articles, optionally filtered by status or search term.")
@useAuth(BearerAuth | ServiceOAuth2<["articles:read"]>)
@opExample(#{
  returnType: #{
    count: 42,
    next: "https://api.example.com/api/v1/articles?page=3",
    previous: "https://api.example.com/api/v1/articles?page=1",
    results: #[
      #{
        id: "art_01HZX3K9P2QY",
        title: "Designing a Contract-First API",
        slug: "designing-a-contract-first-api",
        body: "A contract-first workflow lets backend and frontend teams start in parallel by agreeing on the wire shape up front.",
        status: ArticleStatus.published,
        author_id: "usr_01HZX3K9P2",
        tags: #["api", "typespec"],
        created_at: utcDateTime.fromISO("2026-06-01T10:00:00Z"),
        updated_at: utcDateTime.fromISO("2026-06-02T08:30:00Z"),
      },
      #{
        id: "art_01HZX4M0R3ZB",
        title: "Mocking the Contract with Prism",
        slug: "mocking-the-contract-with-prism",
        body: "Prism turns the OpenAPI document into a live mock so the frontend can build before the backend exists.",
        status: ArticleStatus.draft,
        author_id: "usr_01HZX3K9P2",
        tags: #["prism", "mock"],
        created_at: utcDateTime.fromISO("2026-06-03T09:15:00Z"),
        updated_at: utcDateTime.fromISO("2026-06-03T09:15:00Z"),
      }
    ],
  },
})
op listArticles(
  @doc("1-based page number.")
  @query
  page?: int32 = 1,

  @doc("Number of items per page.")
  @query
  page_size?: int32 = 20,

  @doc("Filter by publication status.")
  @query
  status?: ArticleStatus,

  @doc("Full-text search query.")
  @query
  search?: string,
): ListResponse<Article> | UnauthorizedError | ForbiddenError | RateLimitError;

@tag("articles")
@route("/api/v1/articles")
@post
@summary("Create an article")
@doc("Create a new article.")
@useAuth(BearerAuth | ServiceOAuth2<["articles:write"]>)
@opExample(#{
  parameters: #{
    body: #{
      title: "Designing a Contract-First API",
      body: "A contract-first workflow lets backend and frontend teams start in parallel by agreeing on the wire shape up front.",
      tags: #["api", "typespec"],
      status: ArticleStatus.published,
    },
  },
  returnType: #{
    statusCode: 201,
    body: #{
      id: "art_01HZX3K9P2QY",
      title: "Designing a Contract-First API",
      slug: "designing-a-contract-first-api",
      body: "A contract-first workflow lets backend and frontend teams start in parallel by agreeing on the wire shape up front.",
      status: ArticleStatus.published,
      author_id: "usr_01HZX3K9P2",
      tags: #["api", "typespec"],
      created_at: utcDateTime.fromISO("2026-06-01T10:00:00Z"),
      updated_at: utcDateTime.fromISO("2026-06-02T08:30:00Z"),
    },
  },
})
@opExample(#{
  returnType: #{
    statusCode: 400,
    body: #{ errors: #[#{ field: "title", code: "required", message: "This field is required." }] },
  },
})
@opExample(#{
  returnType: #{ statusCode: 409, body: #{ detail: "An article with this slug already exists." } },
})
op createArticle(
  @doc("Article creation payload.")
  @body
  body: ArticleCreate,
):
  | {
      @statusCode statusCode: 201;

      @doc("The created article.")
      @body
      body: Article;
    }
  | ValidationError
  | UnauthorizedError
  | ForbiddenError
  | ConflictError
  | RateLimitError;

@tag("articles")
@route("/api/v1/articles/{id}")
@get
@summary("Get an article")
@doc("Retrieve a single article by its identifier.")
@useAuth(BearerAuth | ServiceOAuth2<["articles:read"]>)
@opExample(#{
  returnType: #{
    id: "art_01HZX3K9P2QY",
    title: "Designing a Contract-First API",
    slug: "designing-a-contract-first-api",
    body: "A contract-first workflow lets backend and frontend teams start in parallel by agreeing on the wire shape up front.",
    status: ArticleStatus.published,
    author_id: "usr_01HZX3K9P2",
    tags: #["api", "typespec"],
    created_at: utcDateTime.fromISO("2026-06-01T10:00:00Z"),
    updated_at: utcDateTime.fromISO("2026-06-02T08:30:00Z"),
  },
})
@opExample(#{
  returnType: #{ statusCode: 404, body: #{ detail: "Article not found." } },
})
op getArticle(
  @doc("Article identifier.")
  @path
  id: string,
):
  | Article
  | UnauthorizedError
  | ForbiddenError
  | NotFoundError
  | RateLimitError;

@tag("articles")
@route("/api/v1/articles/{id}")
@patch
@summary("Update an article")
@doc("Partially update an existing article.")
@useAuth(BearerAuth | ServiceOAuth2<["articles:write"]>)
@opExample(#{
  parameters: #{ id: "art_01HZX3K9P2QY", body: #{ status: ArticleStatus.archived } },
  returnType: #{
    id: "art_01HZX3K9P2QY",
    title: "Designing a Contract-First API",
    slug: "designing-a-contract-first-api",
    body: "A contract-first workflow lets backend and frontend teams start in parallel by agreeing on the wire shape up front.",
    status: ArticleStatus.archived,
    author_id: "usr_01HZX3K9P2",
    tags: #["api", "typespec"],
    created_at: utcDateTime.fromISO("2026-06-01T10:00:00Z"),
    updated_at: utcDateTime.fromISO("2026-06-04T11:45:00Z"),
  },
})
@opExample(#{
  returnType: #{ statusCode: 404, body: #{ detail: "Article not found." } },
})
op updateArticle(
  @doc("Article identifier.")
  @path
  id: string,

  @doc("Article update payload.")
  @body
  body: ArticleUpdate,
):
  | Article
  | ValidationError
  | UnauthorizedError
  | ForbiddenError
  | NotFoundError
  | ConflictError
  | RateLimitError;

@tag("articles")
@route("/api/v1/articles/{id}")
@delete
@summary("Delete an article")
@doc("Delete an existing article.")
@useAuth(BearerAuth | ServiceOAuth2<["articles:write"]>)
@opExample(#{
  returnType: #{ statusCode: 404, body: #{ detail: "Article not found." } },
})
op deleteArticle(
  @doc("Article identifier.")
  @path
  id: string,
):
  | {
      @statusCode statusCode: 204;
    }
  | UnauthorizedError
  | ForbiddenError
  | NotFoundError
  | RateLimitError;
