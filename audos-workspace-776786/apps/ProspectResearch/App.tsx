import { useMemo, useState } from 'react';
import {
  Target,
  Search,
  Users,
  Building,
  ClipboardCheck,
  Copy,
  Check,
  ExternalLink,
  Flag,
  Globe,
  MapPin,
  AlertCircle,
  BookOpen,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Content source: docs/b2b-prospect-spec.md (B2B Prospect Research Spec,
// ReloPass target accounts, FR→NO corridor — produced 2026-07-16 from public
// web sources). This app is the founder-facing viewer for that research.
// ---------------------------------------------------------------------------

const APOLLO_BOOLEAN = `(subsea OR offshore OR "offshore wind" OR "floating wind" OR "\u00e9olien en mer" OR hydrogen OR hydrog\u00e8ne OR "oil and gas" OR "oil & gas" OR parap\u00e9trolier OR "marine engineering" OR geophysics OR g\u00e9ophysique OR seismic OR sismique) AND (Norway OR Norv\u00e8ge OR norv\u00e9gien OR "North Sea" OR "mer du Nord" OR "Norwegian Continental Shelf" OR NCS OR Equinor OR Stavanger OR Haugesund OR "Utsira Nord")`;

const APOLLO_BOOLEAN_TIGHT = `("Norway" OR "Norv\u00e8ge" OR "Equinor" OR "Norwegian") AND ("subsea" OR "offshore" OR "hydrogen" OR "\u00e9olien" OR "oil and gas")`;

const SALESNAV_KEYWORDS = `(Norway OR Norv\u00e8ge OR Equinor OR "North Sea" OR "mer du Nord" OR Stavanger) AND (offshore OR subsea OR hydrogen OR hydrog\u00e8ne OR \u00e9olien OR "oil and gas")`;

const HR_TITLES_EN = [
  'HR Director', 'Human Resources Director', 'Head of HR', 'Head of People',
  'HR Manager', 'People & Culture Manager', 'HR Business Partner',
  'Global Mobility Manager', 'International Mobility Manager',
  'Compensation & Benefits Manager', 'Talent Manager',
];

const HR_TITLES_FR = [
  'DRH', 'Directeur des Ressources Humaines', 'Directrice des Ressources Humaines',
  'Responsable Ressources Humaines', 'Responsable RH',
  'Responsable Mobilit\u00e9 Internationale', 'Charg\u00e9 de Mobilit\u00e9 Internationale',
  'Charg\u00e9e de Mobilit\u00e9 Internationale', 'Responsable Paie et Administration du Personnel',
  'Responsable D\u00e9veloppement RH', 'HRBP',
];

interface Segment {
  name: string;
  whyNorway: string;
  headcount: string;
  examples: string;
}

const SEGMENTS: Segment[] = [
  {
    name: 'Subsea & marine offshore services contractors',
    whyNorway: 'Installation, IMR and survey campaigns on the Norwegian Continental Shelf; crews mobilize to Stavanger, Haugesund and Bergen for offshore rotations.',
    headcount: '80\u2013400',
    examples: 'JIFMAR Offshore Services (Aix-en-Provence), Louis Dreyfus TravOcean (Marseille), Comex (Marseille)',
  },
  {
    name: 'Offshore & marine engineering consultancies',
    whyNorway: 'FEED/detail engineering for NCS field developments and Norwegian floating-wind projects; engineers seconded to client offices in Norway for months. DORIS has NCS heritage back to Ekofisk.',
    headcount: '50\u2013300',
    examples: 'DORIS Group (Paris), Principia (La Ciotat), Sofresid Engineering (Paris region), Innosea (Nantes \u2014 Oslo-listed parent ABL Group)',
  },
  {
    name: 'Floating offshore wind technology & development',
    whyNorway: "Norway's Utsira Nord 500 MW floating-wind award (Dec 2025) went to the EDF power solutions \u00d7 Deep Wind Offshore JV, pulling the French floating-wind supply chain toward Haugesund. BW Ideol is Oslo-listed with Norwegian parent BW Offshore.",
    headcount: '30\u2013150',
    examples: 'BW Ideol (La Ciotat), Eolink (Brest), Valorem (Bordeaux area)',
  },
  {
    name: 'Hydrogen & Power-to-X project companies',
    whyNorway: 'Nordic green-H2/ammonia build-out with Norwegian partners: Lhyfe has an MoU with Horisont Energi for green ammonia and partners with Norwegian electrolyser maker Hystar; project teams travel to Oslo/Stavanger regularly.',
    headcount: '100\u2013300',
    examples: 'Lhyfe (Nantes), HDF Energy (Bordeaux), McPhy (Grenoble), Elogen (Paris region), Genvia (B\u00e9ziers)',
  },
  {
    name: 'Oil & gas field services, manpower & inspection',
    whyNorway: 'Specialist technicians, welders and inspectors supplied to NCS operators and Equinor/TotalEnergies supplier contracts \u2014 classic rotation-heavy workforces.',
    headcount: '100\u2013500',
    examples: 'SeaOwl (Paris), Serimax (Roissy), Ponticelli offshore division (entry point into a larger group)',
  },
  {
    name: 'Geoscience, seismic & subsurface services',
    whyNorway: 'NCS exploration/4D monitoring and the growing Norwegian CCS market; the French-Norwegian Chamber even ran a CCS & Geoscience mission from Pau, the historic French petroleum-geoscience hub.',
    headcount: '20\u2013200 (skews small)',
    examples: 'RealTimeSeismic (Pau), MAPPEM Geophysics (Brest), Geostock (Rueil-Malmaison)',
  },
  {
    name: 'Subsea robotics, monitoring & marine digital tech',
    whyNorway: 'Norwegian offshore operators are early adopters of subsea autonomy and digital fleet ops; French firms sell into NCS projects and send field engineers for offshore commissioning.',
    headcount: '50\u2013200',
    examples: 'Forssea Robotics (Paris), Cybernetix (Marseille, TechnipFMC group), Opsealog (Marseille)',
  },
];

interface Company {
  name: string;
  city: string;
  headcount: string;
  fit: string;
  website: string;
  flag?: string;
}

const COMPANIES: Company[] = [
  { name: 'DORIS Group', city: 'Paris', headcount: '~230', fit: 'Offshore engineering with NCS heritage (Ekofisk, Troll); active in offshore wind and CCS studies', website: 'doris-engineering.com' },
  { name: 'BW Ideol', city: 'La Ciotat', headcount: '~80\u2013100', fit: 'Floating-wind technology; Norwegian parent BW Offshore, listed Euronext Growth Oslo; DNV cert awarded at Haugesund', website: 'bw-ideol.com' },
  { name: 'Principia', city: 'La Ciotat', headcount: '~100', fit: 'Marine/offshore structural & hydrodynamics engineering (moorings, floaters) for North Sea and floating-wind clients', website: 'principia.fr' },
  { name: 'Sofresid Engineering', city: 'Montreuil (Paris)', headcount: '~150\u2013250', fit: 'Marine & offshore engineering (hulls, topsides, offshore wind substations)', website: 'sofresid-engineering.com' },
  { name: 'Innosea (ABL Group)', city: 'Nantes', headcount: '~40\u201360', fit: 'Marine-renewables engineering consultancy; parent ABL Group is Oslo-listed \u2014 direct Norwegian reporting lines', website: 'innosea.fr', flag: 'Below 50 \u2014 monitor' },
  { name: 'D-ICE Engineering', city: 'Nantes', headcount: '~60\u201390', fit: 'Marine control systems & naval-tech R&D; Nordic/polar operations focus', website: 'dice-engineering.com' },
  { name: 'Lhyfe', city: 'Nantes', headcount: '~200', fit: 'Green hydrogen; MoU with Horisont Energi (NO); partners Norwegian electrolyser maker Hystar; member of Norwegian Hydrogen Forum', website: 'lhyfe.com' },
  { name: 'HDF Energy', city: 'Blanquefort (Bordeaux)', headcount: '~100\u2013150', fit: 'Hydrogen power plants & multi-MW fuel cells; maritime-decarbonization partnerships relevant to Norwegian shipping', website: 'hdf-energy.com' },
  { name: 'Elogen (GTT group)', city: 'Les Ulis (Paris)', headcount: '~150', fit: 'PEM electrolyser manufacturer supplying European/Nordic H2 projects', website: 'elogenh2.com' },
  { name: 'McPhy Energy', city: 'Grenoble', headcount: '~200\u2013250', fit: 'Electrolysers & hydrogen stations deployed across Northern Europe', website: 'mcphy.com' },
  { name: 'Genvia', city: 'B\u00e9ziers', headcount: '~150\u2013200', fit: 'High-temperature electrolysis (SLB/CEA JV); industrial H2 pilots with Nordic relevance', website: 'genvia.com' },
  { name: 'JIFMAR Offshore Services', city: 'Aix-en-Provence', headcount: '~300\u2013400', fit: 'Multi-purpose offshore vessel & marine-services group working North-European offshore energy campaigns', website: 'jifmar.com' },
  { name: 'Louis Dreyfus TravOcean', city: 'Marseille', headcount: '~80\u2013120', fit: 'Submarine cable installation for offshore wind & interconnectors, incl. North Sea work', website: 'ld-travocean.com' },
  { name: 'Louis Dreyfus Armateurs (offshore-wind BU)', city: 'Suresnes', headcount: '~500 (group)', fit: 'Service-operation vessels for offshore wind, built to Norwegian ship designs (Salt Ship Design); Nordic charters', website: 'lda.fr', flag: 'Edge of band' },
  { name: 'SeaOwl', city: 'Paris', headcount: '~400\u2013500', fit: 'O&G operations manpower, ROV & integrity services \u2014 rotation-heavy staffing for operators incl. TotalEnergies affiliates', website: 'seaowlgroup.com' },
  { name: 'Comex', city: 'Marseille', headcount: '~100', fit: 'Subsea engineering & hyperbaric testing; historic North Sea diving contractor, still serves offshore clients', website: 'comex.fr' },
  { name: 'Cybernetix (TechnipFMC)', city: 'Marseille', headcount: '~120\u2013180', fit: 'Subsea robotics & asset-monitoring systems delivered into NCS projects via TechnipFMC', website: 'cybernetix.fr' },
  { name: 'Forssea Robotics', city: 'Paris', headcount: '~50\u201370', fit: 'Subsea robotics/ROVs and smart winches for offshore wind & O&G survey campaigns', website: 'forssea-robotics.fr' },
  { name: 'Opsealog', city: 'Marseille', headcount: '~50\u201370', fit: 'Fleet performance digitalization for offshore/marine operators incl. North-European fleets', website: 'opsealog.com' },
  { name: 'Geostock', city: 'Rueil-Malmaison', headcount: '~200', fit: 'Underground energy storage & CCS engineering; Norwegian CCS market (Northern Lights ecosystem) relevance', website: 'geostockgroup.com' },
  { name: 'Valorem', city: 'B\u00e8gles (Bordeaux)', headcount: '~400', fit: 'Independent renewables developer expanding into Nordic markets and offshore wind consortia', website: 'valorem-energie.com' },
  { name: 'Le B\u00e9on Manufacturing', city: 'Lorient', headcount: '~80\u2013120', fit: 'Mooring & lifting hardware for offshore energy and floating wind (supply chain for Norwegian floating projects)', website: 'lebeon.fr' },
  { name: 'Serimax', city: 'Roissy (Paris)', headcount: '~500', fit: 'Pipeline welding specialist with North Sea / NCS pipeline project history', website: 'serimax.com', flag: 'Edge of band' },
  { name: 'RealTimeSeismic', city: 'Pau', headcount: '~30\u201350', fit: 'Seismic acquisition & processing services from the Pau geoscience hub', website: 'realtimeseismic.com', flag: 'Below 50 \u2014 monitor' },
  { name: 'MAPPEM Geophysics', city: 'Brest', headcount: '~20\u201340', fit: 'Marine electromagnetic geophysics for offshore site surveys', website: 'mappem-geophysics.com', flag: 'Below 50 \u2014 monitor' },
  { name: 'Eolink', city: 'Brest', headcount: '~30\u201350', fit: 'Floating-wind turbine technology developer; scaling with pilot projects', website: 'eolink.fr', flag: 'Below 50 \u2014 monitor' },
  { name: 'Ter\u00e9ga', city: 'Pau', headcount: '~650', fit: 'Gas/H2/CO2 transport infrastructure; Pau energy hub; above band but a corridor-relevant HR org worth a bespoke approach', website: 'terega.fr', flag: 'Above band' },
];

const ANCHOR_ACCOUNTS = [
  { name: 'TechnipFMC', note: 'Awarded multiple 2026 Equinor subsea contracts (Brime, Omega S\u00f8r, Tyrihans Nord, Troll); its French staff rotate to Norway constantly \u2014 mine its mid-size French subcontractors.' },
  { name: 'Technip Energies', note: 'NCS and Norwegian energy-transition projects.' },
  { name: 'Viridien (ex-CGG) & Sercel', note: 'Geoscience anchors with Norway offices.' },
  { name: 'Nexans', note: 'Owns Nexans Norway (Halden subsea-cable plant); heavy FR\u2194NO traffic.' },
  { name: 'Vallourec, Saipem SA, Ponticelli, Bourbon', note: 'Offshore supply-chain giants whose French project teams and subcontractors work NCS scopes.' },
  { name: 'TotalEnergies EP Norge & EDF power solutions', note: 'Corridor demand generators: TotalEnergies co-sponsors the French SME mission to ONS Stavanger; EDF\u2019s JV with Deep Wind Offshore won Utsira Nord (500 MW, Dec 2025).' },
];

const ECOSYSTEM_SOURCES = [
  { name: 'Evolen (evolen.org)', note: '~300 French energy-industry members; runs the Mission Norv\u00e8ge \u2013 ONS 2026 (Stavanger, 25\u201326 Aug 2026) with an Equinor HQ visit. The published delegation list = pre-qualified FR\u2192NO prospects.' },
  { name: 'CCI France Norv\u00e8ge / CCFN (ccfn.no)', note: '~150 members, \u00c9nergie + Offshore Wind committees, a member directory, and an RH committee (HR contacts already corridor-aware).' },
  { name: 'UFE / MEDEF energy committees', note: 'Policy-level lists; GEP-AFTP (petroleum association) merged into Evolen, so Evolen membership covers it.' },
  { name: 'Team Norway France / Norwegian Business Association', note: 'Via Innovation Norway Paris & businessnorway.com \u2014 names French partners in offshore-wind articles and events.' },
  { name: 'Equinor supplier announcements (equinor.com)', note: 'Each NCS contract wave names contractors whose French subsidiaries mobilize staff to Norway.' },
];

const SEARCH_LOG = [
  'French subsea company Norway operations offshore contractors 2026',
  'French offshore wind companies Norway projects floating wind Norwegian waters',
  'Chambre de Commerce Franco-Norv\u00e9gienne membres entreprises fran\u00e7aises Norv\u00e8ge \u00e9nergie',
  'Lhyfe HDF Energy McPhy hydrogen Norway partnership Nordic projects French hydrogen companies',
  'Evolen members French oil gas services companies Norway ONS Stavanger delegation entreprises fran\u00e7aises parap\u00e9trolier',
  'Doris Engineering Ponticelli Entrepose Saipem France offshore Norway North Sea projects French engineering companies',
  'BW Ideol La Ciotat floating wind Norway Oslo listed employees Innosea ABL Group Nantes',
];

const FOLLOWUP_QUERIES = [
  'site:ccfn.no "Trouver un membre" \u2014 scrape the CCFN member directory for energy members',
  'Evolen ONS 2026 d\u00e9l\u00e9gation liste entreprises \u2014 capture the delegation roster when published (Aug 2026)',
  'Equinor supplier register French companies Achilles JQS \u2014 French firms in Equinor\u2019s qualification system',
  '"Utsira Nord" supply chain fran\u00e7ais \u2014 French suppliers announced on the Harald H\u00e5rfagre project',
  'Per company: "<company>" Norway OR Norv\u00e8ge site:linkedin.com \u2014 confirm live corridor activity before outreach',
];

type TabId = 'overview' | 'apollo' | 'salesnav' | 'segments' | 'companies' | 'log';

const TABS: { id: TabId; label: string; Icon: any }[] = [
  { id: 'overview', label: 'Overview & ICP', Icon: Target },
  { id: 'apollo', label: 'Apollo.io', Icon: Search },
  { id: 'salesnav', label: 'Sales Navigator', Icon: Users },
  { id: 'segments', label: 'Segments', Icon: ClipboardCheck },
  { id: 'companies', label: 'Companies', Icon: Building },
  { id: 'log', label: 'Search Log', Icon: BookOpen },
];

function CopyBlock({ label, text }: { label: string; text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (e.g. no permission) — user can select manually
    }
  };
  return (
    <div className="rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)] overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--space-border-default)]">
        <span className="text-xs font-semibold text-[var(--space-text-secondary)]">{label}</span>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-[var(--space-surface-accent-soft)] text-[var(--space-text-accent)] hover:brightness-110 transition-all"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="px-3 py-3 text-xs leading-relaxed whitespace-pre-wrap break-words text-[var(--space-text-primary)] font-mono">{text}</pre>
    </div>
  );
}

function Chips({ items }: { items: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map(item => (
        <span key={item} className="px-2.5 py-1 rounded-full text-xs bg-[var(--space-surface-accent-soft)] text-[var(--space-text-primary)] border border-[var(--space-border-default)]">
          {item}
        </span>
      ))}
    </div>
  );
}

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-4 space-y-3">
      <h3 className="text-sm font-semibold text-[var(--space-text-primary)]">{title}</h3>
      {children}
    </div>
  );
}

function FilterRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-[160px_1fr] gap-1 sm:gap-3 py-2 border-b border-[var(--space-border-default)] last:border-b-0">
      <div className="text-xs font-semibold text-[var(--space-text-accent)]">{label}</div>
      <div className="text-xs text-[var(--space-text-primary)] leading-relaxed">{value}</div>
    </div>
  );
}

export default function ProspectResearch() {
  const [tab, setTab] = useState<TabId>('overview');
  const [companyFilter, setCompanyFilter] = useState('');

  const filteredCompanies = useMemo(() => {
    const q = companyFilter.trim().toLowerCase();
    if (!q) return COMPANIES;
    return COMPANIES.filter(c =>
      [c.name, c.city, c.fit, c.website].join(' ').toLowerCase().includes(q)
    );
  }, [companyFilter]);

  return (
    <div className="h-full flex flex-col bg-[var(--space-surface-page)]">
      {/* Header */}
      <div className="px-5 pt-5 pb-3">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--space-surface-accent-soft)] flex items-center justify-center flex-shrink-0">
            <Target className="w-5 h-5 text-[var(--space-text-accent)]" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-[var(--space-text-primary)]">B2B Prospect Research — FR→NO Corridor</h1>
            <p className="text-xs text-[var(--space-text-secondary)] mt-0.5">
              Target accounts for ReloPass: French energy companies (50–500 staff) that routinely send employees to Norway.
              Research from public sources, 16 Jul 2026 · Source file: <span className="font-mono">docs/b2b-prospect-spec.md</span>
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="px-5 flex gap-1.5 flex-wrap border-b border-[var(--space-border-default)] pb-3">
        {TABS.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              tab === id
                ? 'bg-[var(--space-brand-primary)] text-[var(--space-text-on-primary)]'
                : 'bg-[var(--space-surface-muted)] text-[var(--space-text-secondary)] hover:bg-[var(--space-surface-panel-strong)]'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
            {id === 'companies' && <span className="opacity-70">({COMPANIES.length})</span>}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
        {tab === 'overview' && (
          <>
            <SectionCard title="Why this ICP">
              <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed">
                French energy companies — subsea, offshore wind, hydrogen, oil & gas services, marine engineering,
                geophysics — routinely rotate or post staff to Norway: North Sea operations, Equinor supplier contracts,
                Norwegian JVs, and floating-wind projects in Norwegian waters (Utsira Nord). Mid-size firms (50–500
                employees) are the sweet spot: they send people abroad but rarely have an in-house global-mobility team,
                so they buy relocation support externally. The buying contact is the HR Director / Head of People (DRH,
                Responsable RH) or, where it exists, a Global Mobility manager.
              </p>
            </SectionCard>
            <SectionCard title="ICP hard constraints">
              <div>
                <FilterRow label="Company size" value="50–500 employees" />
                <FilterRow label="HQ geography" value="France — priority hubs: Paris region, Marseille/Aix–La Ciotat, Bordeaux, Pau, Le Havre, plus Nantes–Saint-Nazaire and Brest (marine-energy clusters)" />
                <FilterRow label="Industry" value="Energy: subsea contractors, offshore wind developers/technology, hydrogen project companies, oil & gas services, marine engineering, geophysics/seismic" />
                <FilterRow label="Corridor relevance" value="Regularly sends employees to Norway: NCS operations, Equinor supplier contracts, Norwegian JVs or parents, Norwegian offshore-wind projects" />
              </div>
            </SectionCard>
            <SectionCard title="How to use this research">
              <ol className="text-xs text-[var(--space-text-secondary)] leading-relaxed list-decimal pl-4 space-y-1">
                <li>Paste the Apollo.io tab’s filters and boolean string into Apollo; same for Sales Navigator.</li>
                <li>Cross-check hits against the Segments and the 27-company starter list.</li>
                <li>Verify headcount and Norway relevance per company before outreach — estimates drift, and flagged entries sit at the edge of the 50–500 band.</li>
              </ol>
            </SectionCard>
          </>
        )}

        {tab === 'apollo' && (
          <>
            <SectionCard title="Company filters">
              <div>
                <FilterRow label="Industry (Apollo taxonomy)" value="Oil & Energy · Renewables & Environment · Maritime · Mechanical or Industrial Engineering · Utilities · Civil Engineering" />
                <FilterRow label="# Employees" value="51–100, 101–200, 201–500 (select all three brackets)" />
                <FilterRow label="Company HQ location" value="Country = France. Hub passes: Paris, Marseille, Aix-en-Provence, La Ciotat, Bordeaux, Pau, Le Havre, Nantes, Saint-Nazaire, Brest" />
                <FilterRow label="Company keywords" value="subsea · offshore · offshore wind · floating wind · éolien en mer · hydrogen · hydrogène · oil and gas · parapétrolier · marine engineering · naval · geophysics · géophysique · seismic · sismique · North Sea · Norway · Norvège · Equinor · NCS" />
              </div>
            </SectionCard>
            <SectionCard title="HR contact — job titles (English)">
              <Chips items={HR_TITLES_EN} />
            </SectionCard>
            <SectionCard title="HR contact — job titles (French)">
              <Chips items={HR_TITLES_FR} />
              <p className="text-xs text-[var(--space-text-muted)]">
                Seniority: Director, Head, Manager, VP — include Owner/C-Suite for companies under ~100 employees (the CEO/CFO often owns HR there).
              </p>
            </SectionCard>
            <CopyBlock label="Boolean search string (copy-paste)" text={APOLLO_BOOLEAN} />
            <CopyBlock label="Tighter variant — companies that name-drop Norway explicitly" text={APOLLO_BOOLEAN_TIGHT} />
          </>
        )}

        {tab === 'salesnav' && (
          <>
            <SectionCard title="Account (company) search">
              <div>
                <FilterRow label="Headquarters location" value="Country: France. Regional passes: Île-de-France · Provence-Alpes-Côte d'Azur (Marseille/La Ciotat) · Nouvelle-Aquitaine (Bordeaux + Pau) · Normandy (Le Havre) · Pays de la Loire (Nantes/Saint-Nazaire) · Brittany (Brest)" />
                <FilterRow label="Company headcount" value="51–200 and 201–500" />
                <FilterRow label="Industry" value="Oil and Gas · Renewable Energy Power Generation · Services for Renewable Energy · Maritime Transportation · Shipbuilding · Engineering Services · Industrial Machinery Manufacturing · Utilities" />
                <FilterRow label="Keywords (accounts)" value='subsea OR offshore OR "offshore wind" OR hydrogène OR "oil and gas" OR géophysique OR "marine engineering"' />
              </div>
            </SectionCard>
            <SectionCard title="Lead (people) search — run inside the saved account list">
              <div>
                <FilterRow label="Job title (English)" value="HR Director OR Head of HR OR Head of People OR HR Manager OR Human Resources Manager OR HR Business Partner OR Global Mobility OR International Mobility OR Compensation and Benefits" />
                <FilterRow label="Job title (French)" value="DRH OR Directeur des Ressources Humaines OR Directrice des Ressources Humaines OR Responsable Ressources Humaines OR Responsable RH OR Responsable Mobilité Internationale OR Chargée de Mobilité" />
                <FilterRow label="Seniority level" value="Director, Manager, VP, CXO (CXO catches DRH-as-C-level and small-company CEOs)" />
                <FilterRow label="Function" value="Human Resources" />
              </div>
            </SectionCard>
            <CopyBlock label="Keywords panel input (copy-paste)" text={SALESNAV_KEYWORDS} />
            <SectionCard title="Buying-signal tip">
              <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed">
                Run a posted-content search for accounts whose employees post about ONS Stavanger, Utsira Nord, Equinor
                contracts, or the CCFN/Evolen Norway missions — posting about the ONS 2026 mission (25–26 Aug 2026,
                Stavanger) is a strong live buying signal.
              </p>
            </SectionCard>
          </>
        )}

        {tab === 'segments' && (
          <>
            {SEGMENTS.map((s, i) => (
              <SectionCard key={s.name} title={`${i + 1}. ${s.name}`}>
                <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed">{s.whyNorway}</p>
                <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs">
                  <span className="text-[var(--space-text-muted)]">Headcount: <span className="text-[var(--space-text-primary)] font-medium">{s.headcount}</span></span>
                </div>
                <p className="text-xs text-[var(--space-text-primary)]"><span className="text-[var(--space-text-muted)]">Examples: </span>{s.examples}</p>
              </SectionCard>
            ))}
          </>
        )}

        {tab === 'companies' && (
          <>
            <div className="flex items-center gap-2 rounded-xl border border-[var(--space-border-default)] bg-[var(--space-surface-muted)] px-3 py-2">
              <Search className="w-4 h-4 text-[var(--space-text-muted)] flex-shrink-0" />
              <input
                type="text"
                value={companyFilter}
                onChange={e => setCompanyFilter(e.target.value)}
                placeholder="Filter by name, city, or keyword…"
                className="flex-1 bg-transparent text-sm text-[var(--space-text-primary)] placeholder:text-[var(--space-text-muted)] outline-none"
              />
              <span className="text-xs text-[var(--space-text-muted)]">{filteredCompanies.length}/{COMPANIES.length}</span>
            </div>
            <p className="text-xs text-[var(--space-text-muted)]">
              ⚠️ Headcounts are public estimates — verify in Apollo before scoring. Flagged entries sit at or near the edge of the 50–500 band.
            </p>
            {filteredCompanies.map(c => (
              <div key={c.name} className="rounded-2xl border border-[var(--space-border-default)] bg-[var(--space-surface-panel)] p-4">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-[var(--space-text-primary)]">{c.name}</h3>
                    {c.flag && (
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-[var(--space-surface-muted)] text-[var(--space-semantic-warning)] border border-[var(--space-border-default)]">
                        <AlertCircle className="w-3 h-3" />{c.flag}
                      </span>
                    )}
                  </div>
                  <a
                    href={`https://${c.website}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-xs text-[var(--space-text-accent)] hover:underline"
                  >
                    {c.website}<ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <div className="flex flex-wrap gap-x-5 gap-y-1 mt-1.5 text-xs text-[var(--space-text-muted)]">
                  <span className="flex items-center gap-1"><MapPin className="w-3 h-3" />{c.city}</span>
                  <span className="flex items-center gap-1"><Users className="w-3 h-3" />{c.headcount} employees</span>
                </div>
                <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed mt-2">{c.fit}</p>
              </div>
            ))}
            <SectionCard title="Anchor accounts above 500 employees (referrals & ecosystem mapping, not core ICP)">
              <ul className="space-y-2">
                {ANCHOR_ACCOUNTS.map(a => (
                  <li key={a.name} className="text-xs leading-relaxed">
                    <span className="font-semibold text-[var(--space-text-primary)]">{a.name}</span>
                    <span className="text-[var(--space-text-secondary)]"> — {a.note}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
            <SectionCard title="Ecosystem sources for continuous list-building">
              <ul className="space-y-2">
                {ECOSYSTEM_SOURCES.map(s => (
                  <li key={s.name} className="text-xs leading-relaxed">
                    <span className="font-semibold text-[var(--space-text-primary)] inline-flex items-center gap-1"><Globe className="w-3 h-3 text-[var(--space-text-accent)]" />{s.name}</span>
                    <span className="text-[var(--space-text-secondary)]"> — {s.note}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
          </>
        )}

        {tab === 'log' && (
          <>
            <SectionCard title="Queries executed (16 Jul 2026, general web search)">
              <ol className="text-xs text-[var(--space-text-secondary)] leading-relaxed list-decimal pl-4 space-y-1">
                {SEARCH_LOG.map(q => <li key={q} className="font-mono">{q}</li>)}
              </ol>
            </SectionCard>
            <SectionCard title="Key sources consulted">
              <p className="text-xs text-[var(--space-text-secondary)] leading-relaxed">
                equinor.com (2026 NCS subsea contract awards) · offshore-mag.com · offshore-energy.biz · offshorewind.biz
                (Utsira Nord award, Dec 2025) · deepwindoffshore.com (EDF JV) · businessnorway.com · lhyfe.com press room
                (Horisont Energi MoU; Hystar partnership) · hdf-energy.com · ccfn.no (committees, ONS 2026 mission,
                ~150 members) · evolen.org (Mission Norvège ONS 2026, ~300 members) · bw-ideol.com + annual report
                (Oslo listing, La Ciotat HQ) · LinkedIn company pages · ponticelli.com · simdex.com
              </p>
            </SectionCard>
            <SectionCard title="Recommended follow-up queries (not yet run)">
              <ul className="text-xs text-[var(--space-text-secondary)] leading-relaxed space-y-1.5">
                {FOLLOWUP_QUERIES.map(q => (
                  <li key={q} className="flex items-start gap-1.5">
                    <Flag className="w-3 h-3 mt-0.5 flex-shrink-0 text-[var(--space-text-accent)]" />
                    <span>{q}</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
          </>
        )}
      </div>
    </div>
  );
}
