import { motion } from "framer-motion";
import qsvaLogoBlack from "@/assets/qsva-logo-black.png";

const stats = [
  { value: "Post‑Quantum", label: "Cryptographic Foundation" },
  { value: "Zero‑Trust", label: "Execution Model" },
  { value: "AI‑Resilient", label: "By Design" },
];

const Hero = () => {
  return (
    <section className="min-h-screen flex flex-col justify-center relative overflow-hidden">
      {/* Subtle grid pattern */}
      <div className="absolute inset-0 opacity-[0.03]" style={{
        backgroundImage: `linear-gradient(hsl(var(--foreground)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--foreground)) 1px, transparent 1px)`,
        backgroundSize: '60px 60px',
      }} />

      {/* Radial glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full opacity-[0.04]" style={{
        background: 'radial-gradient(circle, hsl(var(--foreground)) 0%, transparent 70%)',
      }} />

      <div className="max-w-6xl mx-auto px-6 lg:px-8 pt-32 pb-16 w-full">
        <div className="grid lg:grid-cols-[1fr_auto] gap-16 items-center">
          <div className="max-w-2xl">
            <motion.div
              initial={{ opacity: 0, width: 0 }}
              animate={{ opacity: 1, width: "3rem" }}
              transition={{ duration: 0.8, delay: 0.1 }}
              className="h-px bg-foreground mb-8"
            />

            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              className="text-xs font-medium tracking-[0.2em] uppercase text-muted-foreground mb-6"
            >
              Execution‑Time Authorization
            </motion.p>

            <motion.h1
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.7, delay: 0.3 }}
              className="font-serif text-5xl md:text-6xl lg:text-7xl leading-[1.05] tracking-tight text-foreground mb-8"
            >
              Security Controls
              <br />
              <span className="text-muted-foreground/60">For Agents</span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="text-base md:text-lg text-muted-foreground leading-relaxed mb-10 max-w-lg"
            >
              Cryptographically prove a real human approved a specific action at execution time
              across agentic AI, hardware systems, and high‑risk enterprise workflows.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.7 }}
              className="flex flex-col sm:flex-row gap-4 items-start"
            >
              <a
                href="https://calendly.com/ben-qsva/30min"
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-center px-7 py-3.5 rounded-md bg-primary text-primary-foreground font-medium text-sm hover:bg-primary/90 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10"
              >
                Talk to the QSVA Team
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" className="ml-2 transition-transform duration-300 group-hover:translate-x-1">
                  <path d="M3 8h10m0 0L9 4m4 4L9 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </a>
              <a
                href="#waitlist"
                onClick={(e) => { e.preventDefault(); document.querySelector('#waitlist')?.scrollIntoView({ behavior: 'smooth' }); }}
                className="inline-flex items-center px-7 py-3.5 rounded-md border border-input text-foreground font-medium text-sm hover:bg-accent transition-all duration-300"
              >
                Join the Waitlist
              </a>
            </motion.div>
          </div>

          {/* Decorative logo mark */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 0.04, scale: 1 }}
            transition={{ duration: 1.2, delay: 0.4 }}
            className="hidden lg:block"
          >
            <img src={qsvaLogoBlack} alt="" className="w-72 xl:w-80 select-none pointer-events-none" aria-hidden="true" />
          </motion.div>
        </div>
      </div>

      {/* Stats bar */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6, delay: 1 }}
        className="max-w-6xl mx-auto px-6 lg:px-8 w-full pb-24"
      >
        <div className="border-t border-border pt-10">
          <div className="grid grid-cols-3 gap-8">
            {stats.map((stat, i) => (
              <motion.div
                key={stat.label}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.4, delay: 1.2 + i * 0.15 }}
                className="text-center lg:text-left"
              >
                <p className="text-sm md:text-base font-semibold text-foreground tracking-tight">{stat.value}</p>
                <p className="text-xs text-muted-foreground mt-1 tracking-wide">{stat.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Bottom decorative line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-border" />
    </section>
  );
};

export default Hero;
