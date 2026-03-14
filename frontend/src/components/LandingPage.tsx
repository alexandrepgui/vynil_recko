import { useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion, useInView } from 'framer-motion';
import logoIcon from '../assets/icon.svg';
import vinylRecord from '../assets/vinyl-spinner.svg';

/* ── Scroll-triggered reveal wrapper ─────────────────────────────────── */

function Reveal({ children, className, delay = 0 }: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef(null);
  const inView = useInView(ref, { margin: '-80px', amount: 0.3 });

  return (
    <motion.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 36 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, ease: 'easeOut', delay }}
    >
      {children}
    </motion.div>
  );
}

/* ── Before / After animated transition ──────────────────────────────── */

const BEFORE_STEPS = [
  'Pull out a record',
  'Squint at the label',
  'Open Discogs',
  'Type in what you think you read',
  'Scroll through 30 pressings',
  'Compare catalog numbers',
  'Find your exact release (maybe)',
  'Add to collection',
  'Repeat \u00d7 200',
];

const AFTER_STEPS = [
  'Snap a photo of the label',
  'We find the right pressing',
  'You approve',
];

function BeforeAfter() {
  return (
    <div className="landing-ba">
      <div className="landing-ba-side">
        <h3 className="landing-ba-heading landing-ba-heading--before">The old way</h3>
        <ol className="landing-ba-list landing-ba-list--long">
          {BEFORE_STEPS.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
        <p className="landing-ba-verdict">
          &ldquo;I&rsquo;ll do it this weekend.&rdquo; <em>(You won&rsquo;t.)</em>
        </p>
      </div>
      <div className="landing-ba-divider" />
      <div className="landing-ba-side">
        <h3 className="landing-ba-heading landing-ba-heading--after">With Groove Log</h3>
        <ol className="landing-ba-list landing-ba-list--short">
          {AFTER_STEPS.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>
        <p className="landing-ba-verdict landing-ba-verdict--done">Done.</p>
      </div>
    </div>
  );
}

/* ── How-it-works steps ──────────────────────────────────────────────── */

const STEPS = [
  {
    num: '1',
    title: 'Snap',
    desc: 'Take a photo of the record label. That\u2019s\u00a0it.',
  },
  {
    num: '2',
    title: 'We search',
    desc: 'We read the catalog number, artist, and label \u2014 and find the right pressing on Discogs. Not just any version \u2014 yours.',
  },
  {
    num: '3',
    title: 'You approve',
    desc: 'Review matches in a queue. Accept, reject, retry if necessary. Your collection builds\u00a0itself.',
  },
];

/* ── Why-catalog reasons ─────────────────────────────────────────────── */

const WHY_REASONS = [
  {
    title: 'No more duplicate gifts',
    desc: 'Share your collection with friends and family. They\u2019ll know exactly what you have \u2014 and what you\u2019re missing.',
  },
  {
    title: 'Buy, sell, exchange',
    desc: 'Know what you own, what it\u2019s worth, what you\u2019d trade. No more guessing at the record fair.',
  },
  {
    title: 'Treat it with care',
    desc: 'You chose every record for a reason. A catalog is how you honor that.',
  },
];

/* ── Export formats ───────────────────────────────────────────────────── */

const EXPORT_FORMATS = [
  { name: 'CSV', aside: null },
  { name: 'Excel', aside: null },
  { name: 'PDF', aside: null },
  { name: 'Obsidian', aside: '(yes)' },
];

/* ── Main component ──────────────────────────────────────────────────── */

export default function LandingPage() {
  const navigate = useNavigate();
  const handleGetStarted = () => navigate('/login');

  return (
    <div className="landing">
      {/* ── Navbar ──────────────────────────────────────────────────── */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-nav-brand">
            <img src={logoIcon} alt="" className="navbar-icon" />
            <span className="navbar-wordmark">groove log</span>
          </div>
          <div className="landing-nav-actions">
            <Link to="/login" className="landing-signin">Sign In</Link>
            <button className="btn btn-primary" onClick={handleGetStarted}>
              Get Started
            </button>
          </div>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────── */}
      <section className="landing-hero">
        <motion.div
          className="landing-hero-brand"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <img src={logoIcon} alt="Groove Log" className="landing-brand-icon" />
        </motion.div>

        <div className="landing-hero-columns">
        <motion.div
          className="landing-hero-text"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
        >
          <h1 className="landing-headline">
            Finally catalog<br />your collection.
          </h1>

          <p className="landing-aside">An app for vinyl people. Yeah, we know. Hear us out.</p>
          <p className="landing-subheadline">
            Searching every record on Discogs, scrolling through pressings,
            matching catalog numbers &mdash; life&rsquo;s too short.
          </p>
          <p className="landing-subheadline landing-subheadline--bold">
            Snap your labels. We do the rest.
          </p>
          <button className="btn btn-primary landing-cta" onClick={handleGetStarted}>
            Start Cataloging
          </button>
        </motion.div>

        <motion.div
          className="landing-hero-visual"
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.8, delay: 0.3 }}
        >
          <div className="landing-vinyl-spin">
            <img src={vinylRecord} alt="" className="landing-vinyl-img" />
          </div>
          <div className="landing-app-mockup">
            <div className="mockup-bar">
              <span className="mockup-dot" />
              <span className="mockup-dot" />
              <span className="mockup-dot" />
            </div>
            <div className="mockup-body">
              <div className="mockup-upload-zone">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="17 8 12 3 7 8" />
                  <line x1="12" y1="3" x2="12" y2="15" />
                </svg>
                <span>Upload label photo</span>
              </div>
              <div className="mockup-results">
                <div className="mockup-result" />
                <div className="mockup-result mockup-result--match" />
                <div className="mockup-result" />
              </div>
            </div>
          </div>
        </motion.div>
        </div>
      </section>

      {/* ── Before / After ─────────────────────────────────────────── */}
      <Reveal className="landing-section">
        <BeforeAfter />
      </Reveal>

      {/* ── How It Works ───────────────────────────────────────────── */}
      <section className="landing-section landing-section--alt">
        <Reveal>
          <h2 className="landing-section-title">How it works</h2>
        </Reveal>
        <div className="landing-steps">
          {STEPS.map((step, i) => (
            <Reveal key={i} className="landing-step" delay={i * 0.12}>
              <span className="landing-step-num">{step.num}</span>
              <h3 className="landing-step-title">{step.title}</h3>
              <p className="landing-step-desc">{step.desc}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Batch Mode ─────────────────────────────────────────────── */}
      <Reveal className="landing-section landing-batch">
        <h2 className="landing-section-title">
          Upload 100 labels at once.
        </h2>
        <p className="landing-batch-sub">
          Go make coffee. Come back and review your matches on the couch.
        </p>
      </Reveal>

      {/* ── Why Catalog ────────────────────────────────────────────── */}
      <section className="landing-section landing-section--alt">
        <Reveal>
          <h2 className="landing-section-title">Why catalog?</h2>
          <p className="landing-why-intro">
            Your collection is worth more than a stack of records on a shelf.
          </p>
        </Reveal>
        <div className="landing-why-grid">
          {WHY_REASONS.map((reason, i) => (
            <Reveal key={i} className="landing-why-card" delay={i * 0.1}>
              <h3>{reason.title}</h3>
              <p>{reason.desc}</p>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ── Your Data, Your Way ────────────────────────────────────── */}
      <Reveal className="landing-section landing-data">
        <h2 className="landing-section-title">Your data, your way.</h2>
        <p className="landing-data-philosophy">
          Technology should serve your hobby, not replace it.
          Groove Log is a better filing cabinet for your records &mdash; nothing more.
        </p>
        <ul className="landing-not-list">
          <li>No algorithms telling you what to listen to</li>
          <li>No recommendations, no &ldquo;people who bought this also bought&hellip;&rdquo;</li>
          <li>No selling your data</li>
          <li>No replacing the experience of digging through crates</li>
        </ul>
        <p className="landing-data-philosophy">
          Your records, your taste, your data.
          We just help you take care of what you already love.
        </p>
        <p className="landing-data-export">Export everything. Your collection data belongs to you&nbsp;&mdash;&nbsp;not&nbsp;us.</p>
        <div className="landing-export-badges">
          {EXPORT_FORMATS.map(fmt => (
            <span key={fmt.name} className="landing-export-badge">
              {fmt.name}
              {fmt.aside && <span className="landing-export-aside">{fmt.aside}</span>}
            </span>
          ))}
        </div>
      </Reveal>

      {/* ── CTA Footer ─────────────────────────────────────────────── */}
      <Reveal className="landing-section landing-final-cta">
        <h2 className="landing-section-title">
          You&rsquo;ve been putting this off long enough.
        </h2>
        <button className="btn btn-primary landing-cta" onClick={handleGetStarted}>
          Start Cataloging
        </button>
        <p className="landing-final-sub">Syncs with Discogs</p>
      </Reveal>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <footer className="landing-footer">
        <div className="landing-footer-brand">
          <img src={logoIcon} alt="" className="landing-footer-icon" />
          <span className="landing-footer-wordmark">groove log</span>
        </div>
        <p className="landing-footer-tagline">Built by people who dig through crates too.</p>
      </footer>
    </div>
  );
}
