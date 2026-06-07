import "@typespec/http";

using Http;

namespace ClaudeApiContract;

/**
 * Service-to-service authentication (OAuth2 client-credentials flow).
 * Per-operation scopes drive granular authorization (D5, auth-contract rule).
 */
alias ServiceOAuth2<Scopes extends string[]> = OAuth2Auth<
  [
    {
      type: OAuth2FlowType.clientCredentials;
      tokenUrl: "https://api.example.com/auth/token";
    }
  ],
  Scopes
>;
