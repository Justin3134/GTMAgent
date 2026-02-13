import { Linkedin } from "lucide-react";
import qsvaLogoBlack from "@/assets/qsva-logo-black.png";

const Footer = () => {
  return (
    <footer className="py-16 bg-secondary">
      <div className="max-w-6xl mx-auto px-6 lg:px-8">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-3">
            <img src={qsvaLogoBlack} alt="QSVA" className="h-6 w-auto opacity-60" />
            <span className="text-sm text-muted-foreground">© 2026 QSVA. All rights reserved.</span>
          </div>
          <a
            href="https://www.linkedin.com/company/qsva"
            target="_blank"
            rel="noopener noreferrer"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <Linkedin size={18} />
          </a>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
