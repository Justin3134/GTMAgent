import { motion } from "framer-motion";
import { Linkedin } from "lucide-react";

import benImg from "@/assets/team/ben-zuiker.jpeg";
import tomImg from "@/assets/team/tom-gilheany.jpeg";
import pkImg from "@/assets/team/pk-kumar.jpeg";
import massimoImg from "@/assets/team/massimo-bertaccini.png";
import willImg from "@/assets/team/will-harader.png";
import justinImg from "@/assets/team/justin-kim.jpeg";

const members = [
  {
    name: "Ben Zuiker",
    role: "Co-Founder & CEO",
    bio: "3× founder and cryptographic systems inventor. Previously co-founded Zmt Labs, a cryptography research lab focused on authentication and authorization systems resilient to AI driven and quantum threats.",
    img: benImg,
    linkedin: "https://www.linkedin.com/in/benzuiker/",
  },
  {
    name: "Tom Gilheany",
    role: "Co-Founder, CTO, CISO",
    bio: "Security and AI systems leader with 30+ years building enterprise infrastructure leading next generation security platforms.",
    img: tomImg,
    linkedin: "https://www.linkedin.com/in/tomgilheany/",
  },
  {
    name: "Prof. PK Prasanna Kumar",
    role: "Chief AI Officer",
    bio: "Serial Entrepreneur, Senior Exec across Healthcare, Finance, and AI. Bestselling Author, Adjunct Professor of Applied AI, Expert in AI Powered Platforms.",
    img: pkImg,
    linkedin: "https://www.linkedin.com/in/profpk/",
  },
  {
    name: "Massimo Bertaccini PhD",
    role: "Chief Cryptography Scientist",
    bio: "Cryptography and privacy expert designing production grade cryptographic systems. Co-founder of CryptoLab and inventor of the first cryptographic search engine for encrypted data.",
    img: massimoImg,
    linkedin: "https://www.linkedin.com/in/massimo-bertaccini-phd-7292091b/",
  },
  {
    name: "Will Harader",
    role: "Chief Systems Architect",
    bio: "Senior systems engineer with 30+ years building production software across hardware integrated systems, cloud and AI.",
    img: willImg,
    linkedin: "https://www.linkedin.com/in/william-harader-01b47530/",
  },
  {
    name: "Justin Kim",
    role: "Software Engineer",
    bio: "Full stack engineer with 10+ years building and shipping AI, fintech, and production systems. Former CTO who's led end-to-end development of scalable applications.",
    img: justinImg,
    linkedin: "",
  },
];

const Team = () => {
  return (
    <section id="team" className="py-24 md:py-32 relative">
      <div className="max-w-7xl mx-auto px-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="font-heading text-4xl md:text-5xl font-bold mb-4">The Team</h2>
          <p className="text-muted-foreground text-lg max-w-xl mx-auto">
            Built by experts in cryptography, AI, and enterprise security.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-8">
          {members.map((m, i) => (
            <motion.div
              key={m.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="group rounded-xl border border-border bg-card overflow-hidden hover:border-primary/30 transition-all duration-300"
            >
              <div className="aspect-[4/3] overflow-hidden bg-muted">
                <img
                  src={m.img}
                  alt={m.name}
                  className="w-full h-full object-cover object-top group-hover:scale-105 transition-transform duration-500"
                />
              </div>
              <div className="p-6">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="font-heading text-lg font-semibold text-foreground">{m.name}</h3>
                    <p className="text-sm text-primary font-medium">{m.role}</p>
                  </div>
                  {m.linkedin && (
                    <a
                      href={m.linkedin}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-muted-foreground hover:text-primary transition-colors flex-shrink-0 mt-1"
                    >
                      <Linkedin size={18} />
                    </a>
                  )}
                </div>
                <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{m.bio}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Team;
