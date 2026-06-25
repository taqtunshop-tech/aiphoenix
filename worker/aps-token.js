/**
 * Cloudflare Worker: APS Token Proxy
 * Генерирует 2-часовой access token для Autodesk Platform Services Viewer SDK.
 *
 * Деплой:
 *   npx wrangler deploy
 *
 * Секреты (задаются через wrangler secret put):
 *   APS_CLIENT_ID     — Client ID из Autodesk Developer Portal
 *   APS_CLIENT_SECRET — Client Secret из Autodesk Developer Portal
 */

const APS_BASE = "https://developer.api.autodesk.com";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // CORS headers
    const corsHeaders = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders });
    }

    // Health check
    if (url.pathname === "/api/health") {
      return new Response(JSON.stringify({ ok: true }), {
        headers: { "Content-Type": "application/json", ...corsHeaders },
      });
    }

    // Token endpoint
    if (url.pathname === "/api/token") {
      try {
        const token = await getAccessToken(env.APS_CLIENT_ID, env.APS_CLIENT_SECRET);
        return new Response(JSON.stringify(token), {
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      } catch (err) {
        return new Response(JSON.stringify({ error: err.message }), {
          status: 500,
          headers: { "Content-Type": "application/json", ...corsHeaders },
        });
      }
    }

    return new Response("Not Found", { status: 404, headers: corsHeaders });
  },
};

async function getAccessToken(clientId, clientSecret) {
  const credentials = btoa(`${clientId}:${clientSecret}`);

  const response = await fetch(`${APS_BASE}/authentication/v1/authenticate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${credentials}`,
    },
    body: "grant_type=client_credentials",
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`APS auth failed (${response.status}): ${text}`);
  }

  return await response.json();
}
