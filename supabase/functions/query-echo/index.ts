// Lab function: echo HTTP method/body to test RFC 10008 QUERY support
// through the Supabase Edge (Deno) gateway.
Deno.serve(async (req: Request) => {
  const body = await req.text();
  return new Response(
    JSON.stringify({ runtime: "deno-supabase-edge", method: req.method, body }),
    { headers: { "content-type": "application/json" } },
  );
});
