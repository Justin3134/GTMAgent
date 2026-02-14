import { motion } from "framer-motion";
import { Shield, Cpu, Landmark, Building2, Lock, HeartPulse } from "lucide-react";

const items = [
  {
    title: "Agentic AI Platforms",
    desc: "Automated systems and orchestration layers executing autonomous workflows.",
    icon: Cpu,
  },
  {
    title: "AI Hardware & Edge",
    desc: "Cyber‑physical environments and edge computing where actions are irreversible.",
    icon: Shield,
  },
  {
    title: "Financial Systems",
    desc: "Payment infrastructure and financial execution requiring human authorization.",
    icon: Landmark,
  },
  {
    title: "Government & Defense",
    desc: "Critical infrastructure and mission‑critical systems demanding accountability.",
    icon: Building2,
  },
  {
    title: "Enterprise Security",
    desc: "High‑risk actions beyond IAM that need execution‑time trust verification.",
    icon: Lock,
  },
  {
    title: "Healthcare & Life Sciences",
    desc: "Patient‑critical systems and regulated environments where every action must be traceable.",
    icon: HeartPulse,
  },
];

const BuiltFor = () => {
  return (
    <section id="built-for" className="py-20 md:py-28 bg-secondary relative">
      {/* Decorative vertical line */}
      <div className="absolute top-0 left-1/2 w-px h-24 bg-gradient-to-b from-transparent to-border hidden md:block" />

      <div className="max-w-6xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1] }}
          className="mb-12"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="h-px w-8 bg-foreground" />
            <span className="text-xs font-medium tracking-[0.2em] uppercase text-muted-foreground">Industries</span>
          </div>
          <h2 className="font-serif text-4xl md:text-5xl text-foreground mb-4">
            Built for Autonomous Execution Risk
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl">
            QSVA is built for teams deploying agentic systems where mistakes are irreversible,
            including:
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-px bg-border rounded-lg overflow-hidden">
          {items.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={{ once: true, margin: "-30px" }}
              transition={{ duration: 0.4, delay: i * 0.05, ease: [0.25, 0.1, 0.25, 1] }}
              className="bg-background p-7 lg:p-9 group hover:bg-accent/50 transition-all duration-500 relative"
            >
              {/* Hover accent line */}
              <div className="absolute top-0 left-0 w-0 h-0.5 bg-foreground group-hover:w-full transition-all duration-500" />

              <div className="flex items-start justify-between mb-5">
                <span className="text-xs font-medium tracking-widest uppercase text-muted-foreground/50">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <item.icon size={20} className="text-muted-foreground/30 group-hover:text-foreground/70 transition-colors duration-500" />
              </div>
              <h3 className="text-lg font-semibold text-foreground mb-2">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>

        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.3, delay: 0.1 }}
          className="mt-12 text-center"
        >
          <a
            href="https://calendly.com/ben-qsva/30min"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium text-foreground underline underline-offset-4 decoration-border hover:decoration-foreground transition-colors"
          >
            Talk to the QSVA Team →
          </a>
        </motion.div>
      </div>
    </section>
  );
};

export default BuiltFor;
