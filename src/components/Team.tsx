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
    linkedin: "https://www.linkedin.com/in/junhyun-kim-15840128b/",
  },
];

const Team = () => {
  return (
    <section id="team" className="py-20 md:py-28 bg-secondary">
      <div className="max-w-6xl mx-auto px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.5 }}
          className="mb-12"
        >
          <div className="flex items-center gap-4 mb-4">
            <div className="h-px w-8 bg-foreground" />
            <span className="text-xs font-medium tracking-[0.2em] uppercase text-muted-foreground">Our People</span>
          </div>
          <h2 className="font-serif text-4xl md:text-5xl text-foreground mb-4">Leadership</h2>
          <p className="text-muted-foreground text-lg max-w-xl">
            Built by experts in cryptography, AI, and enterprise security.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-12">
          {members.map((m, i) => (
            <motion.div
              key={m.name}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-50px" }}
              transition={{ duration: 0.5, delay: i * 0.07 }}
              className="group"
            >
              <div className="aspect-[4/5] overflow-hidden rounded-sm bg-accent mb-4 relative">
                <img
                  src={m.img}
                  alt={m.name}
                  className="w-full h-full object-cover object-top grayscale group-hover:grayscale-0 transition-all duration-700 group-hover:scale-[1.02]"
                />
                <div className="absolute inset-0 ring-1 ring-inset ring-foreground/5 rounded-sm" />
              </div>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-base font-semibold text-foreground">{m.name}</h3>
                  <p className="text-sm text-muted-foreground mt-0.5">{m.role}</p>
                </div>
                {m.linkedin && (
                  <a
                    href={m.linkedin}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-foreground transition-colors mt-0.5"
                  >
                    <Linkedin size={16} />
                  </a>
                )}
              </div>
              <p className="mt-3 text-sm text-muted-foreground leading-relaxed">{m.bio}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Team;
