import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
};

const RECIPIENT = "Justin.07823@gmail.com";

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { email, message } = await req.json();

    if (!email || typeof email !== "string") {
      return new Response(JSON.stringify({ error: "Email is required" }), {
        status: 400,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Use Supabase's built-in SMTP to send via the Auth admin API
    // Since we don't have SMTP configured, we'll store in DB and use Resend/other service
    // For now, let's store submissions in a database table
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
        await fetch("https://api.resend.com/emails", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${resendKey}`,
          },
          body: JSON.stringify({
            from: "QSVA Waitlist <onboarding@resend.dev>",
            to: [RECIPIENT],
            subject: `New Waitlist Signup: ${email.trim()}`,
            html: `
              <h2>New Waitlist Submission</h2>
              <p><strong>Email:</strong> ${email.trim()}</p>
              ${message ? `<p><strong>Message:</strong> ${message.trim()}</p>` : ""}
              <hr />
              <p style="color: #888; font-size: 12px;">Sent from QSVA waitlist form</p>
            `,
          }),
        });
      } catch (emailErr) {
        console.error("Email send error:", emailErr);
        // Don't fail the request if email fails - submission is already saved
      }
    } else {
      console.log(`Waitlist submission from ${email.trim()} saved. No RESEND_API_KEY configured for email notifications.`);
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
