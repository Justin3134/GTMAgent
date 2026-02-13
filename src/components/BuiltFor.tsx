import { motion } from "framer-motion";
import { Bot, Cpu, Landmark, Shield, Building2 } from "lucide-react";

const items = [
  {
    icon: Bot,
    title: "Agentic AI Platforms",
    desc: "Automated systems and orchestration layers executing autonomous workflows.",
  },
  {
    icon: Cpu,
    title: "AI Hardware & Edge",
    desc: "Cyber‑physical environments and edge computing where actions are irreversible.",
  },
  {
    icon: Landmark,
    title: "Financial Systems",
    desc: "Payment infrastructure and financial execution requiring human authorization.",
  },
  {
    icon: Shield,
    title: "Government & Defense",
    desc: "Critical infrastructure and mission‑critical systems demanding accountability.",
  },
  {
    icon: Building2,
    title: "Enterprise Security",
    desc: "High‑risk actions beyond IAM that need execution‑time trust verification.",
  },
];

const BuiltFor = () => {
  return (
    <section id="built-for" className="py-24 md:py-32 relative">
      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="font-heading text-4xl md:text-5xl font-bold mb-4">
            Built For
          </h2>
          <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            QSVA is built for teams accountable for execution risk across critical systems.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="group relative rounded-xl border border-border bg-card p-8 hover:border-primary/30 transition-all duration-300 hover:glow-border"
            >
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-5 group-hover:bg-primary/20 transition-colors">
                <item.icon className="w-6 h-6 text-primary" />
              </div>
              <h3 className="font-heading text-lg font-semibold mb-2 text-foreground">{item.title}</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default BuiltFor;
