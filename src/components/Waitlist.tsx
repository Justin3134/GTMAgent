import { useState } from "react";
import { motion } from "framer-motion";

const Waitlist = () => {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    const trimmed = email.trim();
    if (!trimmed) {
      setError("Please enter your email.");
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError("Please enter a valid email address.");
      return;
    }

    setSubmitted(true);
  };

  return (
    <section
      id="waitlist"
      className="py-24 md:py-32 relative overflow-hidden"
      style={{
        backgroundColor: "hsl(var(--inverted-bg))",
        color: "hsl(var(--inverted-fg))",
      }}
    >
      {/* Subtle noise texture */}
      <div className="absolute inset-0 opacity-[0.015]" style={{
        backgroundImage: `radial-gradient(circle at 25% 25%, hsl(var(--inverted-fg)) 1px, transparent 1px)`,
        backgroundSize: '30px 30px',
      }} />

      <div className="max-w-6xl mx-auto px-6 lg:px-8 relative">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="max-w-xl mx-auto text-center"
        >
          <div className="flex items-center justify-center gap-4 mb-4">
            <div className="h-px w-8" style={{ backgroundColor: "hsl(var(--inverted-muted))" }} />
            <span
              className="text-xs font-medium tracking-[0.2em] uppercase"
              style={{ color: "hsl(var(--inverted-muted))" }}
            >
              Early Access
            </span>
            <div className="h-px w-8" style={{ backgroundColor: "hsl(var(--inverted-muted))" }} />
          </div>

          <h2
            className="font-serif text-3xl md:text-4xl mb-4"
            style={{ color: "hsl(var(--inverted-fg))" }}
          >
            Join the Waitlist
          </h2>
          <p
            className="leading-relaxed mb-10"
            style={{ color: "hsl(var(--inverted-muted))" }}
          >
            Be among the first to access QSVA's execution‑time authorization platform.
            We're onboarding select design partners now.
          </p>

          {submitted ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="py-6"
            >
              <div
                className="inline-flex items-center justify-center w-12 h-12 rounded-full border mb-4"
                style={{ borderColor: "hsl(var(--inverted-border))" }}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M4 10.5L8 14.5L16 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="font-medium" style={{ color: "hsl(var(--inverted-fg))" }}>You're on the list.</p>
              <p className="text-sm mt-1" style={{ color: "hsl(var(--inverted-muted))" }}>We'll be in touch soon.</p>
            </motion.div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <div className="flex-1">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full h-12 px-4 rounded-md text-sm transition-shadow focus:outline-none focus:ring-2"
                  style={{
                    backgroundColor: "hsl(var(--inverted-border))",
                    borderColor: "hsl(var(--inverted-border))",
                    color: "hsl(var(--inverted-fg))",
                    border: "1px solid hsl(var(--inverted-border))",
                  }}
                  maxLength={255}
                />
                {error && (
                  <p className="text-xs mt-1.5 text-left" style={{ color: "hsl(0 84% 60%)" }}>{error}</p>
                )}
              </div>
              <button
                type="submit"
                className="h-12 px-7 rounded-md text-sm font-medium transition-all duration-300 hover:opacity-90 whitespace-nowrap"
                style={{
                  backgroundColor: "hsl(var(--inverted-fg))",
                  color: "hsl(var(--inverted-bg))",
                }}
              >
                Request Access
              </button>
            </form>
          )}
        </motion.div>
      </div>
    </section>
  );
};

export default Waitlist;
