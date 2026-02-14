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
    <section id="waitlist" className="py-24 md:py-32 relative overflow-hidden">
      {/* Subtle background texture */}
      <div className="absolute inset-0 opacity-[0.02]" style={{
        backgroundImage: `linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)`,
        backgroundSize: '40px 40px',
      }} />

      {/* Decorative vertical line */}
      <div className="absolute top-0 left-1/2 w-px h-24 bg-gradient-to-b from-transparent to-border hidden md:block" />

      <div className="max-w-6xl mx-auto px-6 lg:px-8 relative">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="max-w-xl mx-auto text-center"
        >
          <div className="flex items-center justify-center gap-4 mb-4">
            <div className="h-px w-8 bg-foreground" />
            <span className="text-xs font-medium tracking-[0.2em] uppercase text-muted-foreground">Early Access</span>
            <div className="h-px w-8 bg-foreground" />
          </div>

          <h2 className="font-serif text-3xl md:text-4xl text-foreground mb-4">
            Join the Waitlist
          </h2>
          <p className="text-muted-foreground leading-relaxed mb-10">
            Be among the first to access QSVA's execution‑time authorization platform.
            We're onboarding select design partners now.
          </p>

          {submitted ? (
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="py-6"
            >
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full border border-foreground/20 mb-4">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M4 10.5L8 14.5L16 6.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="text-foreground font-medium">You're on the list.</p>
              <p className="text-sm text-muted-foreground mt-1">We'll be in touch soon.</p>
            </motion.div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <div className="flex-1">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="w-full h-12 px-4 rounded-md border border-input bg-background text-foreground text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:ring-offset-background transition-shadow"
                  maxLength={255}
                />
                {error && (
                  <p className="text-xs text-destructive mt-1.5 text-left">{error}</p>
                )}
              </div>
              <button
                type="submit"
                className="h-12 px-7 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10 whitespace-nowrap"
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
