import { Linkedin } from "lucide-react";
import qsvaLogoIcon from "@/assets/qsva-logo-icon.png";

const Footer = () => {
  const scrollTo = (id: string) => {
    document.querySelector(id)?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <footer
      className="py-16 md:py-20"
      style={{
        backgroundColor: "hsl(var(--inverted-bg))",
        borderTop: "1px solid hsl(var(--inverted-border))",
      }}
    >
      <div className="max-w-6xl mx-auto px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-[2fr_1fr_1fr] gap-12 md:gap-8 mb-16">
          {/* Brand column */}
          <div>
            <div className="flex items-center gap-2.5 mb-4">
              <img src={qsvaLogoIcon} alt="QSVA" className="h-7 w-auto brightness-0 invert opacity-80" />
              <span
                className="text-base font-semibold tracking-wide"
                style={{ color: "hsl(var(--inverted-fg))" }}
              >
                QSVA
              </span>
            </div>
            <p
              className="text-sm leading-relaxed max-w-xs"
              style={{ color: "hsl(var(--inverted-muted))" }}
            >
              Execution‑time authorization for autonomous systems.
              Cryptographically proving human approval at the moment of action.
            </p>
          </div>

          {/* Navigate column */}
          <div>
            <h4
              className="text-xs font-medium tracking-[0.15em] uppercase mb-5"
              style={{ color: "hsl(var(--inverted-muted))" }}
            >
              Navigate
            </h4>
            <ul className="space-y-3">
              {[
                { label: "About", id: "#about" },
                { label: "Industries", id: "#built-for" },
                { label: "Team", id: "#team" },
                { label: "Waitlist", id: "#waitlist" },
              ].map((link) => (
                <li key={link.id}>
                  <button
                    onClick={() => scrollTo(link.id)}
                    className="text-sm transition-opacity duration-300 hover:opacity-100"
                    style={{ color: "hsl(var(--inverted-muted))", opacity: 0.8 }}
                  >
                    {link.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          {/* Connect column */}
          <div>
            <h4
              className="text-xs font-medium tracking-[0.15em] uppercase mb-5"
              style={{ color: "hsl(var(--inverted-muted))" }}
            >
              Connect
            </h4>
            <ul className="space-y-3">
              <li>
                <a
                  href="https://calendly.com/ben-qsva/30min"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm transition-opacity duration-300 hover:opacity-100"
                  style={{ color: "hsl(var(--inverted-muted))", opacity: 0.8 }}
                >
                  Schedule a Call
                </a>
              </li>
              <li>
                <a
                  href="https://www.linkedin.com/company/qsva"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-2 text-sm transition-opacity duration-300 hover:opacity-100"
                  style={{ color: "hsl(var(--inverted-muted))", opacity: 0.8 }}
                >
                  <Linkedin size={14} />
                  LinkedIn
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Bottom bar */}
        <div
          className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4"
          style={{ borderTop: "1px solid hsl(var(--inverted-border))" }}
        >
          <span className="text-xs" style={{ color: "hsl(var(--inverted-muted))", opacity: 0.6 }}>
            © {new Date().getFullYear()} QSVA Inc. All rights reserved.
          </span>
          <span className="text-xs" style={{ color: "hsl(var(--inverted-muted))", opacity: 0.4 }}>
            San Francisco, CA
          </span>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
