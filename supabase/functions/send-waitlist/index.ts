import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const RECIPIENT = "Justin.07823@gmail.com";

function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email) && email.length <= 255;
}

function validateMessage(msg: string | null | undefined): boolean {
  if (!msg) return true;
  return typeof msg === "string" && msg.length <= 1000;
}

function escapeHtml(unsafe: string): string {
  return unsafe
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, message } = await req.json();

    if (!email || typeof email !== "string" || !validateEmail(email.trim())) {
      return new Response(JSON.stringify({ error: "Invalid email address" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (!validateMessage(message)) {
      return new Response(JSON.stringify({ error: "Message too long (max 1000 characters)" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const supabaseUrl = Deno.env.get("SUPABASE_URL")!;
    const supabaseKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;

    const res = await fetch(`${supabaseUrl}/rest/v1/waitlist_submissions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        apikey: supabaseKey,
        Authorization: `Bearer ${supabaseKey}`,
        Prefer: "return=minimal",
      },
      body: JSON.stringify({
        email: email.trim(),
        message: message?.trim() || null,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      console.error("DB insert error:", errText);
      return new Response(JSON.stringify({ error: "Failed to save submission" }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Send notification email via Resend (if API key is available)
    const resendKey = Deno.env.get("RESEND_API_KEY");
    if (resendKey) {
      try {
        const safeEmail = escapeHtml(email.trim());
        const safeMessage = message ? escapeHtml(message.trim()) : null;

        await fetch("https://api.resend.com/emails", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${resendKey}`,
          },
          body: JSON.stringify({
            from: "QSVA Waitlist <waitlist@qsva.io>",
            to: [RECIPIENT, "ben@qsva.io", "support@qsva.io"],
            subject: `New Waitlist Signup: ${safeEmail}`,
            html: `
              <h2>New Waitlist Submission</h2>
              <p><strong>Email:</strong> ${safeEmail}</p>
              ${safeMessage ? `<p><strong>Message:</strong> ${safeMessage}</p>` : ""}
              <hr />
              <p style="color: #888; font-size: 12px;">Sent from QSVA waitlist form</p>
            `,
          }),
        });
      } catch (emailErr) {
        console.error("Email send error:", emailErr);
      }
    }

    return new Response(JSON.stringify({ success: true }), {
      status: 200,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (err) {
    console.error("Unexpected error:", err);
    return new Response(JSON.stringify({ error: "Internal server error" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
