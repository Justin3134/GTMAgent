import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import BuiltFor from "@/components/BuiltFor";
import About from "@/components/About";
import Team from "@/components/Team";
import Waitlist from "@/components/Waitlist";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <Hero />
      <About />
      <BuiltFor />
      <Team />
      <Waitlist />
      <Footer />
    </div>
  );
};

export default Index;
