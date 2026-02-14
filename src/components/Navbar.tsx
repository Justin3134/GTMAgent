import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { useNavigate, useLocation } from "react-router-dom";
import qsvaLogoBlack from "@/assets/qsva-logo-black.png";

type NavLink = { label: string; href: string; route?: string };

const navLinks: NavLink[] = [
  { label: "Built For", href: "#built-for" },
  { label: "About", href: "#about", route: "/about" },
  { label: "Team", href: "#team" },
  { label: "Waitlist", href: "#waitlist" },
];

const Navbar = () => {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const handleClick = (link: NavLink) => {
    setMobileOpen(false);
    if (link.route) {
      navigate(link.route);
      return;
    }
    if (location.pathname !== "/") {
      navigate("/");
      setTimeout(() => {
        document.querySelector(link.href)?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } else {
      document.querySelector(link.href)?.scrollIntoView({ behavior: "smooth" });
    }
  };

  const handleLogoClick = () => {
    if (location.pathname !== "/") {
      navigate("/");
    } else {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <motion.nav
      initial={{ y: -10, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.4 }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-500 ${
        scrolled ? "bg-background/80 backdrop-blur-xl border-b border-border shadow-sm" : "bg-transparent"
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 lg:px-8 py-4 flex items-center justify-between">
        <a href="#" className="flex items-center gap-2.5" onClick={(e) => { e.preventDefault(); handleLogoClick(); }}>
          <img src={qsvaLogoBlack} alt="QSVA" className="h-9 w-auto" />
          <span className="text-lg font-semibold tracking-wide text-foreground">QSVA</span>
        </a>

        <div className="hidden md:flex items-center gap-8">
          {navLinks.map((link) => (
            <button
              key={link.href}
              onClick={() => handleClick(link)}
              className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-300 relative after:absolute after:bottom-[-2px] after:left-0 after:w-0 after:h-px after:bg-foreground after:transition-all after:duration-300 hover:after:w-full"
            >
              {link.label}
            </button>
          ))}
          <a
            href="https://calendly.com/ben-qsva/30min"
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm font-medium px-5 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-all duration-300 hover:shadow-lg hover:shadow-primary/10"
          >
            Contact
          </a>
        </div>

        <button onClick={() => setMobileOpen(!mobileOpen)} className="md:hidden text-foreground">
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {mobileOpen && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="md:hidden bg-background/95 backdrop-blur-xl border-b border-border px-6 pb-6 space-y-3"
        >
          {navLinks.map((link) => (
            <button
              key={link.href}
              onClick={() => handleClick(link)}
              className="block w-full text-left text-sm text-muted-foreground hover:text-foreground py-2"
            >
              {link.label}
            </button>
          ))}
          <a
            href="https://calendly.com/ben-qsva/30min"
            target="_blank"
            rel="noopener noreferrer"
            className="block text-center text-sm font-medium px-5 py-2.5 rounded-md bg-primary text-primary-foreground"
          >
            Contact
          </a>
        </motion.div>
      )}
    </motion.nav>
  );
};

export default Navbar;
