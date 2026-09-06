import { Link } from "react-router-dom";
import {
  Activity,
  Check,
  FileText,
  MapPin,
  MessageCircle,
  ShieldCheck,
  Stethoscope,
} from "lucide-react";

/**
 * Public marketing landing page — the front door for anyone who is not signed in.
 *
 * Deliberately self-contained: it paints its own warm canvas over the app's
 * cool `body` gradient and carries its own header/footer, so the chrome in
 * App.tsx (which only renders once authenticated) stays out of the way.
 *
 * Every "try the demo" CTA points at /login, the app's sign-in gate.
 */
export default function Landing() {
  return (
    <div className="landing min-h-screen bg-[#faf7f1] text-[#10201c]">
      <LandingHeader />
      <Hero />
      <Mission />
      <Features />
      <Screens />
      <ClosingCta />
      <LandingFooter />
    </div>
  );
}

/* ------------------------------------------------------------------ header */

function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <span className="grid h-8 w-8 place-items-center rounded-[10px] bg-[#0f766e]">
        <MapPin className="h-4 w-4 text-white" strokeWidth={2.2} />
      </span>
      <span className="font-display text-xl font-bold tracking-tight">MedAssist</span>
    </span>
  );
}

const NAV = [
  { label: "About", href: "#mission" },
  { label: "Features", href: "#features" },
  { label: "Screenshots", href: "#screens" },
];

function LandingHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-[#e6e0d5] bg-[#faf7f1]/85 backdrop-blur">
      <div className="mx-auto flex h-[68px] w-full max-w-6xl items-center justify-between px-6">
        <a href="#top" className="shrink-0">
          <Logo />
        </a>

        <nav className="hidden items-center gap-8 text-[15px] text-[#3d4a46] md:flex">
          {NAV.map((item) => (
            <a key={item.href} href={item.href} className="transition hover:text-[#0f766e]">
              {item.label}
            </a>
          ))}
        </nav>

        <Link
          to="/chat"
          className="rounded-full bg-[#0d1c19] px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-[#16302a]"
        >
          Try the demo
        </Link>
      </div>
    </header>
  );
}

/* -------------------------------------------------------------------- hero */

function Hero() {
  return (
    <section id="top" className="relative overflow-hidden">
      <ChartBackdrop />

      <div className="relative mx-auto grid w-full max-w-6xl grid-cols-1 items-center gap-12 px-6 py-16 lg:grid-cols-[1.05fr,0.95fr] lg:py-24">
        <div>
          <span className="inline-flex items-center gap-2 rounded-full border border-[#0f766e]/25 bg-[#0f766e]/[0.07] px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-[#0f5f59]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#f0592b]" />
            MedAssist AI based health assistant
          </span>

          <h1 className="mt-7 font-display text-[clamp(2.5rem,6vw,4.1rem)] font-bold leading-[1.06] tracking-[-0.02em]">
            Healthcare that fits{" "}
            <em className="not-italic font-display italic text-[#0f766e]">in your pocket,</em> not a
            waiting room.
          </h1>

          <div className="mt-9 flex flex-wrap items-center gap-4">
            <Link
              to="/chat"
              className="inline-flex items-center gap-2 rounded-full bg-[#f0592b] px-6 py-3.5 text-[15px] font-semibold text-white shadow-[0_10px_28px_rgba(240,89,43,0.28)] transition hover:bg-[#dc4d22]"
            >
              <Check className="h-4 w-4" strokeWidth={3} />
              Try the live demo
            </Link>
            <a
              href="#features"
              className="rounded-full border border-[#d8d1c4] bg-white px-6 py-3.5 text-[15px] font-semibold text-[#10201c] transition hover:border-[#0f766e]/40"
            >
              Explore features
            </a>
          </div>

          <p className="mt-4 text-[14px] text-[#6b7671]">
            No sign-up required — start chatting as a guest.
          </p>

          <dl className="mt-14 grid max-w-lg grid-cols-3 gap-6">
            <Stat value="4" label="Health tools, one app" />
            <Stat value="AI" label="Symptom & lab insight" />
            <Stat value="24/7" label="First-aid chat support" />
          </dl>
        </div>

        <HeroPhones />
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <dt className="font-display text-3xl font-bold text-[#10201c]">{value}</dt>
      <dd className="mt-1.5 text-[13px] leading-snug text-[#6b7671]">{label}</dd>
    </div>
  );
}

/** Faint EKG-ish polyline that sits behind the hero, echoing the app's theme. */
function ChartBackdrop() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute inset-y-0 right-0 h-full w-[70%] text-[#0f766e]/[0.13]"
      viewBox="0 0 600 400"
      preserveAspectRatio="none"
      fill="none"
    >
      <polyline
        points="0,300 70,255 130,285 200,180 265,225 330,120 400,175 470,90 540,140 600,60"
        stroke="currentColor"
        strokeWidth="2"
      />
      <polyline
        points="0,360 70,330 130,350 200,270 265,300 330,215 400,260 470,190 540,230 600,165"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeDasharray="5 7"
      />
    </svg>
  );
}

function HeroPhones() {
  return (
    <div className="relative mx-auto h-[440px] w-full max-w-[460px] sm:h-[500px]">
      {/* Back phone — dark, first-aid guidance, tucked behind and rotated. */}
      <div className="absolute left-0 top-10 w-[62%] -rotate-6">
        <PhoneFrame tone="dark">
          <Eyebrow tone="dark">First aid</Eyebrow>
          <p className="mt-2 font-display text-lg font-bold text-white">CPR guidance</p>
          <div className="mt-4 rounded-xl bg-white/10 p-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#f5a889]">
              Urgent
            </span>
            <p className="mt-1.5 text-[13px] font-semibold text-white">Step 3 of 6</p>
            <p className="mt-1 text-[12px] leading-relaxed text-white/60">
              Tilt the head back, lift the chin, open the airway.
            </p>
          </div>
        </PhoneFrame>
      </div>

      {/* Front phone — the symptom-check flow. */}
      <div className="absolute right-0 top-0 w-[66%] rotate-[3deg]">
        <PhoneFrame tone="light">
          <Eyebrow tone="light">Symptom check</Eyebrow>
          <p className="mt-2 font-display text-lg font-bold">What&apos;s going on?</p>

          <div className="mt-4 rounded-xl bg-[#e8f2ef] p-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#0f766e]">
              AI match
            </span>
            <p className="mt-1.5 text-[13px] font-semibold">Likely: Seasonal flu</p>
            <p className="mt-1 text-[12px] leading-relaxed text-[#6b7671]">
              3 possible conditions found · rest &amp; fluids advised
            </p>
          </div>

          <div className="mt-3 rounded-xl bg-[#e8f2ef] p-3">
            <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#0f766e]">
              Next step
            </span>
            <p className="mt-1.5 text-[13px] font-semibold">See a doctor if fever &gt; 3 days</p>
            <p className="mt-1 text-[12px] leading-relaxed text-[#6b7671]">
              Based on your reported symptoms
            </p>
          </div>
        </PhoneFrame>
      </div>
    </div>
  );
}

function Eyebrow({ tone, children }: { tone: "dark" | "light"; children: React.ReactNode }) {
  return (
    <span
      className={`font-mono text-[10px] uppercase tracking-[0.16em] ${
        tone === "dark" ? "text-white/55" : "text-[#8b948f]"
      }`}
    >
      {children}
    </span>
  );
}

function PhoneFrame({
  tone,
  children,
}: {
  tone: "dark" | "light";
  children: React.ReactNode;
}) {
  const dark = tone === "dark";
  return (
    <div
      className={`rounded-[30px] p-2.5 shadow-[0_26px_60px_rgba(16,32,28,0.18)] ${
        dark ? "bg-[#22312d]" : "bg-white"
      }`}
    >
      <div
        className={`min-h-[300px] rounded-[22px] p-4 ${
          dark ? "bg-[#2b3a35]" : "bg-white ring-1 ring-[#eae4d9]"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- mission */

function Mission() {
  return (
    <section id="mission" className="scroll-mt-24 border-y border-[#ece6db] bg-[#f4f0e7]">
      <div className="mx-auto grid w-full max-w-6xl grid-cols-1 gap-12 px-6 py-20 lg:grid-cols-[0.9fr,1.1fr]">
        <div>
          <SectionEyebrow>Our mission</SectionEyebrow>
          <h2 className="mt-4 font-display text-[clamp(1.9rem,3.6vw,2.7rem)] font-bold leading-[1.14] tracking-[-0.015em]">
            Answers first. Anxiety later — or never.
          </h2>
        </div>

        <div className="space-y-5 text-[17px] leading-relaxed text-[#4a5652]">
          <p>
            Most health worries start with a question nobody is around to answer. MedAssist sits in
            that gap: describe what you feel, upload a report, or ask what to do right now, and get
            a clear, plain-language read on where you stand.
          </p>
          <p>
            It is not a replacement for a doctor, and it never pretends to be. It grades how urgent
            something looks, explains why, and points you to the right specialist when it is time to
            see one.
          </p>
          <ul className="grid gap-3 pt-2 sm:grid-cols-2">
            {[
              "Plain-language explanations",
              "Severity graded, not guessed",
              "Your history stays encrypted",
              "Specialists near you",
            ].map((point) => (
              <li key={point} className="flex items-start gap-2.5 text-[15px] text-[#10201c]">
                <Check className="mt-0.5 h-4 w-4 shrink-0 text-[#0f766e]" strokeWidth={3} />
                {point}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function SectionEyebrow({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-[#0f5f59]">
      {children}
    </span>
  );
}

/* ---------------------------------------------------------------- features */

const FEATURES = [
  {
    icon: MessageCircle,
    title: "Symptom chat",
    body: "Describe symptoms in your own words. MedAssist asks the follow-up questions a clinician would, then explains what it found.",
  },
  {
    icon: FileText,
    title: "Report & scan analysis",
    body: "Upload lab reports, X-rays, or MRI slices and get the findings translated out of medical shorthand.",
  },
  {
    icon: Activity,
    title: "Severity grading",
    body: "Every assessment comes with an urgency level, so you know the difference between wait-and-see and go-now.",
  },
  {
    icon: Stethoscope,
    title: "Specialist finder",
    body: "Matched to the kind of doctor your case actually calls for, with nearby options pulled from OpenStreetMap.",
  },
];

function Features() {
  return (
    <section id="features" className="scroll-mt-24">
      <div className="mx-auto w-full max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <SectionEyebrow>Features</SectionEyebrow>
          <h2 className="mt-4 font-display text-[clamp(1.9rem,3.6vw,2.7rem)] font-bold leading-[1.14] tracking-[-0.015em]">
            Four tools that cover the moments between doctor visits.
          </h2>
        </div>

        <div className="mt-12 grid gap-5 sm:grid-cols-2">
          {FEATURES.map(({ icon: Icon, title, body }) => (
            <article
              key={title}
              className="rounded-2xl border border-[#e6e0d5] bg-white p-7 transition hover:border-[#0f766e]/35 hover:shadow-[0_16px_40px_rgba(16,32,28,0.07)]"
            >
              <span className="grid h-11 w-11 place-items-center rounded-xl bg-[#e8f2ef]">
                <Icon className="h-5 w-5 text-[#0f766e]" strokeWidth={2} />
              </span>
              <h3 className="mt-5 font-display text-xl font-bold">{title}</h3>
              <p className="mt-2.5 text-[15px] leading-relaxed text-[#5b6763]">{body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ----------------------------------------------------------------- screens */

const SCREENS = [
  {
    eyebrow: "Symptom check",
    title: "A conversation, not a form",
    body: "MedAssist narrows things down one question at a time and shows its reasoning as it goes.",
  },
  {
    eyebrow: "Analyze",
    title: "Reports in plain English",
    body: "Drop in a lab PDF or a scan and see what each finding means for you.",
  },
  {
    eyebrow: "Specialists",
    title: "The right doctor, nearby",
    body: "Ranked matches by specialty, with distance and contact details.",
  },
];

function Screens() {
  return (
    <section id="screens" className="scroll-mt-24 border-y border-[#ece6db] bg-[#f4f0e7]">
      <div className="mx-auto w-full max-w-6xl px-6 py-20">
        <div className="max-w-2xl">
          <SectionEyebrow>Screenshots</SectionEyebrow>
          <h2 className="mt-4 font-display text-[clamp(1.9rem,3.6vw,2.7rem)] font-bold leading-[1.14] tracking-[-0.015em]">
            A look inside the app.
          </h2>
        </div>

        <div className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {SCREENS.map((screen) => (
            <div key={screen.eyebrow}>
              <PhoneFrame tone="light">
                <Eyebrow tone="light">{screen.eyebrow}</Eyebrow>
                <p className="mt-2 font-display text-lg font-bold">{screen.title}</p>
                <div className="mt-4 space-y-3">
                  <div className="h-2.5 w-4/5 rounded-full bg-[#e8f2ef]" />
                  <div className="h-2.5 w-full rounded-full bg-[#eee9de]" />
                  <div className="h-2.5 w-2/3 rounded-full bg-[#eee9de]" />
                  <div className="mt-4 rounded-xl bg-[#e8f2ef] p-3">
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[#0f766e]">
                      MedAssist
                    </span>
                    <div className="mt-2 space-y-2">
                      <div className="h-2 w-full rounded-full bg-white/80" />
                      <div className="h-2 w-3/4 rounded-full bg-white/80" />
                    </div>
                  </div>
                </div>
              </PhoneFrame>
              <p className="mt-5 text-[15px] leading-relaxed text-[#5b6763]">{screen.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------- closing cta */

function ClosingCta() {
  return (
    <section className="mx-auto w-full max-w-3xl px-6 py-24 text-center">
      <h2 className="font-display text-[clamp(2.1rem,5vw,3.2rem)] font-bold leading-[1.1] tracking-[-0.02em]">
        Take control of your health, starting today.
      </h2>
      <p className="mx-auto mt-5 max-w-xl text-[17px] leading-relaxed text-[#5b6763]">
        MedAssist is a working prototype built as a college project — explore the demo to see it in
        action.
      </p>
      <Link
        to="/chat"
        className="mt-9 inline-flex items-center gap-2 rounded-full bg-[#f0592b] px-7 py-4 text-[15px] font-semibold text-white shadow-[0_10px_28px_rgba(240,89,43,0.28)] transition hover:bg-[#dc4d22]"
      >
        <Check className="h-4 w-4" strokeWidth={3} />
        Try the live demo
      </Link>
      <p className="mt-4 text-[14px] text-[#8b948f]">No account needed.</p>
    </section>
  );
}

/* ------------------------------------------------------------------ footer */

function LandingFooter() {
  return (
    <footer className="border-t border-[#e6e0d5]">
      <div className="mx-auto w-full max-w-6xl px-6 py-10">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <Logo />
          <nav className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 text-[15px] text-[#3d4a46]">
            <a href="#mission" className="transition hover:text-[#0f766e]">About Us</a>
            <a href="#features" className="transition hover:text-[#0f766e]">Features</a>
            <a href="#screens" className="transition hover:text-[#0f766e]">Screenshots</a>
            <Link to="/chat" className="transition hover:text-[#0f766e]">Try the demo</Link>
          </nav>
        </div>

        <p className="mt-9 flex items-center justify-center gap-2 text-center text-[14px] text-[#8b948f]">
          <ShieldCheck className="h-4 w-4" strokeWidth={2} />
          MedAssist is an educational prototype and does not provide medical diagnosis.
        </p>
        <p className="mt-2 text-center text-[14px] text-[#8b948f]">
          — MedAssist, your pocket health assistant.
        </p>
      </div>
    </footer>
  );
}
