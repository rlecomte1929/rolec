# ReloPass × CCI Nantes-St Nazaire — Advisor Review & Engineered Prompt

---

## Advisory Review

### The core problem: category mismatch

The attached deck is a **pure investor briefing** — SAFE notes, ARR projections, runway metrics, valuation caps. Hervé Thibaud is not an investor. He is an elected business leader at CCI Nantes-St Nazaire whose job is to **represent SME interests, connect entrepreneurs, and support local economic development**. Sending him an investor deck is the equivalent of pitching a bank loan officer with a VC term sheet — the frames are incompatible and the signal it sends is that you don't know your audience.

### What Hervé Thibaud actually cares about

Based on his CAPEB/CCI profile and the CCI's 2021-2026 mandate:

- He represents **artisans and TPE/PME owners** — the exact companies ReloPass targets
- His CCI role is to **observe, connect, and relay** information between entrepreneurs and public actors
- The CCI's current priorities include **transitions numériques**, **industrie du futur**, **accompagnement à l'international**, and **développement des entreprises**
- He values **peer-to-peer exchange** and openness across sectors — he'll respond to a founder story, not a pitch deck with financial models
- He has **network access to 83,607 companies in Loire-Atlantique**, including the industrial and energy SMEs that are ReloPass's beachhead

### What you actually need from this meeting

Not funding. **Three to five pilot customers.** The CCI is a distribution lever — a warm introduction from Hervé to two engineering SMEs running 20+ cross-border relocations a year is worth more than any slide in your current deck. The pitch goal is: **get him to make those introductions**.

### What to cut entirely

- All financial projections (€0.3M → €0.9M → €2.25M ARR, EBITDA breakeven)
- SAFE / convertible note / valuation cap language
- "18-month runway" framing
- "Why this investor fits" slide
- Norway-first framing (reframe as European startup with strong regional relevance)
- Use of funds breakdown (45% engineering, etc.)

### What to add or reframe

- **Local industrial context**: The Nantes-Saint-Nazaire basin has Naval Group, Airbus, energy sector SMEs, maritime companies — all running cross-border mobility. Name this explicitly.
- **The founder's sector alignment**: Romain's 16 years in international energy projects *is* this region's DNA. Lead with that.
- **CCI mandate alignment**: Connect ReloPass to their "transitions numériques" and "industrie du futur" pillars — it's a natural fit.
- **A concrete ask**: "We are looking for 3 to 5 SMEs in Loire-Atlantique with 10+ international relocations per year to pilot our platform free of charge for 3 months."
- **A partnership slide**: What the CCI could do (introductions, visibility, endorsement) and what ReloPass offers in return (data insights on regional mobility patterns, co-branding on success stories).
- **Language**: The deck should be **in French**. Institutional contacts at the CCI will respond better to French, and it signals you understand the local relationship dynamic.

### Slide structure recommended

| # | Slide | Purpose |
|---|-------|---------|
| 1 | Cover | Product name, one-line value prop, founder name |
| 2 | Le problème | What SMEs experience today — fragmented vendors, no visibility, compliance risk |
| 3 | La solution | Case-centric coordination layer, not an agency or marketplace |
| 4 | Le produit existe | Screenshots, working product, beyond MVP |
| 5 | Pourquoi le bassin Nantes-St Nazaire | Local industries with real cross-border mobility; founder's energy sector background |
| 6 | Qui sommes-nous | Founder profile, 37 discovery interviews, INSEAD EMBA |
| 7 | Ce que nous cherchons | 3-5 SME pilot partners, what it entails, what they get |
| 8 | Comment la CCI peut nous aider | Specific ask + what we bring to the CCI's mandate |
| 9 | Contact & prochaines étapes | One clear call to action |

---

## Engineered Prompt

Use this prompt verbatim with a Claude design or PPTX-capable agent to transform the deck.

---

```
You are a senior startup advisor and presentation designer. Your task is to completely transform an investor pitch deck into a product/partnership pitch targeting a specific institutional contact. Here is everything you need.

---

### INPUT FILE
File: "ReloPass presentation 2026-06-14.pptx"
This is an 11-slide investor briefing for a €500k SAFE raise. It contains financial projections, runway metrics, valuation language, and investor-specific framing. None of this is relevant for the new target audience.

---

### PRODUCT CONTEXT (ReloPass)
ReloPass is a SaaS coordination platform for cross-border employee relocation, targeting SMEs running 10+ international moves per year. It is NOT a relocation agency, marketplace, or immigration law firm. It is the case-management and workflow layer that sits above existing vendors (immigration, housing, tax, schooling, shipping). Key facts:
- A working product already exists (cases, policy-linked guidance, document workflows, provider coordination)
- 37 customer discovery interviews completed (30 relocated employees, 7 HR/mobility buyers)
- Target buyer: HR & Global Mobility managers in engineering and industrial SMEs
- The core insight: cross-border relocation is a coordination problem, not a services problem
- Founded in Norway, expanding across Europe
- Founder: Romain Lecomte, 16 years in international energy sector project management, INSEAD EMBA

---

### TARGET AUDIENCE
**Hervé Thibaud**, élu (elected business representative) at the **CCI Nantes-St Nazaire** (Chambre de Commerce et d'Industrie).
- He is an artisan/SME business owner (construction sector, CAPEB member) who sits on the CCI board
- His role: represent TPE/PME interests, connect entrepreneurs across sectors, relay information between businesses and public actors
- He is NOT an investor and has no investment mandate
- He values peer-to-peer conversation, openness, and practical grounding
- The CCI he represents serves 83,607 companies in Loire-Atlantique, including major industrial players (Naval Group, Airbus, energy sector) in the Saint-Nazaire / Nantes basin
- CCI 2021-2026 mandate priorities: transitions numériques, industrie du futur, accompagnement à l'international, développement des entreprises

---

### PITCH GOAL
Get Hervé Thibaud to introduce ReloPass to 3-5 SMEs in Loire-Atlantique that run 10+ cross-border employee relocations per year. These will serve as paid pilot customers.
- This is NOT a funding ask
- This is a partnership/pilot ask
- The tone should be: entrepreneur speaking to a peer who can open doors

---

### OUTPUT REQUIREMENTS

**Language**: French throughout (except product name "ReloPass" stays in English)

**Slide count**: 9 slides maximum

**Design**: Keep the existing visual identity (navy #0b2b43, teal #1f8e8b, Inter font). Maintain professional dark/light contrast. Remove any slides or elements that reference investor-specific content.

**Slide structure to produce** (create new slides; do not simply patch the existing ones):

**Slide 1 — Couverture**
- Title: "ReloPass"
- Subtitle: "La coordination de mobilité internationale, enfin structurée."
- One-liner: "ReloPass donne aux PME industrielles un outil pour piloter leurs relocalisations transfrontalières — sans changer leurs prestataires."
- Presented by: Romain Lecomte, Fondateur
- Date: Juin 2026

**Slide 2 — Le problème que vivent vos entreprises membres**
- Header: "Une PME qui recrute à l'international coordonne en moyenne 6 à 9 prestataires par dossier — sans outil commun."
- Four pain points (icons + short text):
  1. "Cinq prestataires, cinq boîtes mail" — chaque déménagement = cinq silos
  2. "Personne ne peut répondre : où en est ce dossier ?" — le statut vit dans des threads
  3. "La politique RH est découverte après coup" — les exceptions se négocient au cas par cas
  4. "L'échec retombe sur les RH" — retards, missions ratées, escalades
- Footer: "Ce n'est pas un problème de prestataires. C'est un problème de coordination — et aujourd'hui, aucun outil n'en est propriétaire."

**Slide 3 — La solution : un dossier, une source de vérité**
- Header: "ReloPass est la couche de coordination au-dessus des prestataires existants."
- Three columns (HR, Employé, Prestataires):
  - HR & Mobilité: "Le cockpit du portefeuille. Politique appliquée à la création du dossier. Visibilité temps réel. Piste d'audit intégrée."
  - Employé: "Sa vue personnalisée. Liste de tâches séquencée. Un seul dépôt de documents. Il sait toujours où il en est."
  - Prestataires: "Briefés autour du dossier, pas de l'email. Les prestataires existants restent en place."
- Key message box: "Pas une agence. Pas une place de marché. La couche de coordination au-dessus."

**Slide 4 — Le produit existe**
- Header: "Un produit fonctionnel — au-delà d'un MVP."
- Left: screenshot placeholder (HR case record view) with label "RH — Tableau de bord dossier"
- Right: screenshot placeholder (employee checklist view) with label "Employé — Plan de relocalisation"
- Body text: "Dossiers, guidances liées aux politiques, workflows documentaires et coordination prestataire : tout est opérationnel. Ce cycle de financement finance la validation commerciale, pas l'invention."
- Bottom stat row: "37 entretiens de découverte | 30 salariés relocalisés | 7 acheteurs RH & Mobilité"

**Slide 5 — Pourquoi le bassin Nantes - Saint-Nazaire**
- Header: "Le territoire a exactement le profil d'entreprises que nous ciblons."
- Three points:
  1. "Industries à forte mobilité internationale" — Naval Group, Airbus, énergies marines, sous-traitance industrielle : des PME qui recrutent en Europe et au-delà
  2. "L'ancrage du fondateur" — 16 ans de gestion de projets internationaux dans le secteur de l'énergie. Ce problème, Romain l'a vécu des deux côtés.
  3. "Un levier de compétitivité territoriale" — Les PME qui savent accueillir des talents internationaux recrutent mieux, retiennent mieux, et gagnent en attractivité.
- Align with CCI mandate: "S'inscrit directement dans les priorités CCI 2021-2026 : transitions numériques, industrie du futur, accompagnement à l'international."

**Slide 6 — Qui sommes-nous**
- Header: "Construit par quelqu'un qui a vécu le problème."
- Founder block: Photo placeholder | Romain Lecomte, Fondateur
  - "16 ans à piloter des projets internationaux multi-pays dans le secteur de l'énergie — l'environnement exact où la coordination de relocalisation se grippe."
  - "Vécu le problème en tant que salarié relocalisé et en tant que manager."
  - "INSEAD EMBA. 37 entretiens de découverte avant d'écrire une ligne de code produit."
- Right column — "Ce que nous construisons autour du plan" :
  - "Produit & ingénierie : durcissement du produit existant et déploiement du policy builder"
  - "Conseillers : recrutement d'experts en mobilité, RH-tech et go-to-market"
  - "Partenaires terrain : entreprises pilotes pour valider la tarification et la rétention"

**Slide 7 — Ce que nous cherchons : des PME pilotes**
- Header: "3 à 5 PME en Loire-Atlantique pour un pilote de 3 mois."
- Profile of target company:
  - "PME industrielle ou d'ingénierie"
  - "10+ relocalisations transfrontalières par an"
  - "Une équipe RH ou Mobilité qui gère aujourd'hui par email et tableur"
- What the pilot includes:
  - "Accès complet à la plateforme — sans frais pendant la phase pilote"
  - "Onboarding accompagné (2h de setup + support dédié)"
  - "À l'issue : rapport de coordination et économies de temps quantifiées"
- What we ask:
  - "Un retour structuré à 30 et 90 jours"
  - "La possibilité de citer l'entreprise comme référence si le résultat est concluant"

**Slide 8 — Comment la CCI Nantes - St Nazaire peut nous aider**
- Header: "Une collaboration concrète, pas une demande abstraite."
- Two columns:
  Left — "Ce que nous demandons" :
    - "2 à 3 introductions à des PME membres avec 10+ relocalisations/an"
    - "Une mention dans vos canaux entreprises si le pilote est concluant"
    - "Votre lecture du tissu économique local pour affiner notre ciblage"
  Right — "Ce que ReloPass apporte à la CCI" :
    - "Un outil concret aligné sur vos priorités 'transitions numériques' et 'industrie du futur'"
    - "Des données agrégées sur les flux de mobilité internationale des PME du territoire (anonymisées)"
    - "Un cas d'usage de startup locale à partager avec votre réseau d'entrepreneurs"
- Bottom callout box: "Nous ne demandons pas un financement. Nous demandons des portes."

**Slide 9 — Prochaines étapes**
- Header: "Un échange de 30 minutes pour identifier les bonnes entreprises."
- Three-step visual:
  1. "Rencontre" — 30 min pour vous présenter le produit en live
  2. "Identification" — 2 à 3 entreprises membres qui correspondent au profil
  3. "Introduction" — Email d'introduction ou mise en relation directe
- Contact block:
  - Romain Lecomte
  - romain_lecomte@hotmail.com
  - relopass.com
- Closing line: "ReloPass aide les PME à accueillir les talents internationaux dont elles ont besoin pour grandir. Avec votre réseau, nous pouvons le prouver sur le terrain."

---

### STRICT EXCLUSIONS — do not include anywhere in the deck:
- Any reference to fundraising, SAFE, convertible notes, valuation caps, or investment rounds
- Financial projections or ARR targets
- "18-month runway" or any runway language
- "Use of funds" breakdown
- Churn rate, CAC, LTV, or any SaaS financial metrics
- "Why this investor fits" language
- The phrase "seed round"

---

### DESIGN NOTES:
- Use the existing navy (#0b2b43) and teal (#1f8e8b) brand colors
- Slide 1 (cover) and Slide 9 (closing) should use dark navy background with white text
- Content slides (2-8) should use white/light background with navy text
- Every slide needs at least one visual element (icon, stat callout, column layout, or image placeholder)
- No decorative color bars or accent stripes
- No bullet-heavy text walls — max 3-4 lines per text block
- Font: Inter (or Calibri as safe fallback)
- Slide numbers in bottom right corner: "X / 9 — ReloPass"

---

### QUALITY CHECK before delivering:
1. Extract text from the output and verify zero investor/fundraising language appears
2. Confirm all 9 slides are present with correct structure
3. Confirm the deck is entirely in French (except "ReloPass")
4. Visual QA: convert to images, check for overflow, overlapping elements, and missing content
5. Confirm the ask on Slide 8 is specific and actionable — not vague
```

---

## Notes for Romain

A few things to have ready before the meeting itself:

**Prepare one local example.** If you can name one company in the Nantes-Saint-Nazaire basin (even anonymized as "une PME de sous-traitance navale à Saint-Nazaire") that matches the profile, the conversation becomes concrete immediately. Even a hypothetical is better than abstract.

**Send the deck before the meeting, not during it.** A CCI élu has limited time and reads things in advance. Send a 3-line email with the deck attached 3-4 days before: "Je développe un outil de coordination de mobilité internationale pour les PME industrielles. Je cherche 3 entreprises pilotes dans le bassin Nantes-St Nazaire. Je voudrais vous présenter ça en 30 min."

**The ask should come early in the conversation.** Don't wait for slide 8. Open with: "Je ne cherche pas d'investissement — je cherche des introductions à des PME membres qui relocalisent des salariés à l'international." This immediately reframes the meeting and makes Hervé's job easy.

**Follow up with a specific name.** If he says "oui je connais peut-être des entreprises", have a follow-up email ready that day with the pilot offer in writing, so he has something concrete to forward.
