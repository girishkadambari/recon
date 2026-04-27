# Same Domain Deployment Strategy

This documentation elaborates on the single-domain deployment strategy for the SettleProof MVP to avoid cross-origin (CORS) complexity and reduce domain sprawl overhead.

## Core Strategy

Both the frontend single-page application (SPA) and the backend API are hosted under the same public URL: \`https://cloud.settleproof.app\`.

This simplifies browser cookie management automatically avoiding third-party tracker mitigations, tightens SSL setups securely under one certificate, and simplifies OAuth redirection strictly to native hostname boundaries.

**Routing Rules:**
*   **Backend / API:**
    *   \`cloud.settleproof.app/api/*\` -> proxies internally to FastAPI
    *   \`cloud.settleproof.app/docs\` -> proxies internally to FastAPI Swagger UI
    *   \`cloud.settleproof.app/openapi.json\` -> proxies internally to FastAPI Spec
*   **Frontend / UI:**
    *   \`cloud.settleproof.app/ui/*\` -> Serves the built Vite/React static assets

## Server Configurations

Apache (or an equivalent reverse proxy like NGINX) is leveraged to enforce these routing rules natively before traffic ever reaches the application layers. 

### Web Server Execution
1.  Static frontend assets are extracted to a known directory (e.g., \`/var/www/settleproof-ui\`).
2.  Apache binds an \`Alias\` mapping \`/ui\` natively to this un-protected directory ensuring instant asset delivery bypassing compute overhead.
3.  Rewrite conditions ensure that if an explicit file or directory isn't matched inside the SPA, the browser receives `index.html` (crucial for TanStack router deep-links to survive reloads).
4.  \`ProxyPass\` commands capture the RESTful routes (\`/api/\`) mapping them into the Docker container serving FastAPI on port 8000.  

## Local Test Mappings
When validating this infrastructure natively, you duplicate the public logic pointing strictly at `localhost:8080`.
By simulating the exact alias rules and proxy bridges, local testing uncovers subtle path resolution bugs seamlessly.

Refer to `docs/apache-settleproof.conf` and `docs/apache-local-settleproof.conf` for exact implementation templates.
