import "@typespec/http";
import "@typespec/openapi";
import "./models/security.tsp";
import "./models/pagination.tsp";
import "./models/errors.tsp";
import "./articles.tsp";
import "./auth.tsp";

using Http;
using OpenAPI;

@service(#{ title: "Claude API Contract" })
@doc("REST API contract for the Claude ecosystem: standardized list/error envelopes, JWT user-flow and OAuth2 client-credentials service-flow auth, and a blog-style articles resource. Single source of truth, consumed by claude-django and claude-react-mui.")
@info(#{
  version: "0.1.0",
  contact: #{
    name: "claude-api-contract",
    url: "https://github.com/VadayI/claude-api-contract",
    email: "VadayI@users.noreply.github.com",
  },
  license: #{
    name: "Proprietary",
    url: "https://github.com/VadayI/claude-api-contract",
  },
})
@server("http://localhost:4010", "Prism mock")
@tagMetadata(
  "auth",
  #{
    description: "Authentication: user-flow (register/login/refresh/logout) and service-flow (client-credentials token).",
  }
)
@tagMetadata(
  "articles",
  #{ description: "Blog-style article resource (CRUD)." }
)
@useAuth(BearerAuth)
namespace ClaudeApiContract;
