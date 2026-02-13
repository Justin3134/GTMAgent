import { Linkedin } from "lucide-react";

const Footer = () => {
  return (
    <footer className="border-t border-border py-16">
      <div className="max-w-7xl mx-auto px-6">
        {/* CTA */}
        <div className="text-center mb-16">
          <h2 className="font-heading text-3xl md:text-4xl font-bold mb-4">
            Ready to secure agentic execution?
          </h2>
          <p className="text-muted-foreground mb-8 max-w-lg mx-auto">
            Talk to the QSVA team about bringing execution‑time trust to your autonomous systems.
          </p>
          <a
            href="https://calendly.com/ben-qsva/30min"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-primary text-primary-foreground font-heading font-semibold hover:opacity-90 transition-all glow-button"
          >
            Talk to the QSVA Team
          </a>
        </div>

        {/* Bottom bar */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 pt-8 border-t border-border">
          <div className="flex items-center gap-3">
            <svg width="24" height="24" viewBox="0 0 100 100" fill="none">
              <polygon points="50,5 90,27.5 90,72.5 50,95 10,72.5 10,27.5" stroke="currentColor" strokeWidth="3" fill="none" className="text-primary" />
              <polygon points="50,20 75,35 75,65 50,80 25,65 25,35" stroke="currentColor" strokeWidth="2" fill="none" className="text-primary/60" />
            </svg>
            <span className="text-sm text-muted-foreground">© 2026 QSVA. All rights reserved.</span>
          </div>
          <a
            href="https://www.linkedin.com/company/qsva"
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-primary transition-colors"
          >
            <Linkedin size={20} />
          </a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
