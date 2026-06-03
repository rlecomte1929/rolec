# Azure Support Ticket — Document Intelligence West Europe Residency Confirmation

**Submit at:** `https://portal.azure.com` → Help + support → New support request
**Issue type:** Technical
**Service:** Azure AI services → Document Intelligence
**Problem type:** Configuration and setup
**Problem subtype:** Service location / data residency
**Severity:** B (Moderate) — pre-production compliance question

---

## Pre-submit checklist

- [ ] You have an active Azure subscription with a Document Intelligence resource deployed in **West Europe** (or you can deploy one immediately).
- [ ] You know which specific prebuilt model(s) you'll be using — for ReloPass that's **prebuilt-idDocument** (and possibly prebuilt-document).
- [ ] You have your Azure tenant ID and subscription ID handy for the ticket form.

---

## Ticket title

> Confirmation request: Document Intelligence (prebuilt-idDocument) — in-region processing guarantee for West Europe deployment

---

## Ticket body (copy-paste into the description field)

Hello Azure Support,

I'm planning a production deployment of Azure Document Intelligence (prebuilt-idDocument model) for ReloPass, a B2B SaaS platform supporting cross-border employee relocations. We process identity documents — primarily passports — for employees whose data falls under GDPR Article 9 (biometric data when used for identification).

We are deploying the Document Intelligence resource in **West Europe** for GDPR data residency. Before we proceed to production, I need **written confirmation on a few points** that I can attach to our GDPR Article 30 RoPA and DPIA.

**What I need confirmed in writing**

1. **In-region processing guarantee.** When a Document Intelligence resource is deployed in West Europe and we call `prebuilt-idDocument` against it, is the actual inference (model invocation, OCR, MRZ extraction) performed in West Europe — or is the request routed to a different Azure region (e.g. East US) for the prebuilt-model inference layer?

   I'm asking because Microsoft Q&A threads and the cross-region failover documentation suggest some Azure AI Services route the inference layer to a "primary" region distinct from the customer-deployed resource region. I need to know whether prebuilt-idDocument is one of those, or whether it's strictly in-region.

2. **At-rest data location.** When `prebuilt-idDocument` processes an uploaded image, where is the request payload at rest during the processing window? Specifically: is it stored in West Europe-located storage only, or does it transit through another region?

3. **Logs and telemetry.** Are the operational logs (request metadata, error logs, performance telemetry) for our resource stored exclusively in West Europe, or do they replicate to other regions?

4. **Customer Lockbox compatibility.** Is Customer Lockbox for Microsoft Azure compatible with Document Intelligence in West Europe for this scenario?

5. **Sub-processor list.** Does Microsoft engage any sub-processor for the prebuilt-idDocument inference layer that would put data outside the EU/EEA?

**Why I need this**

Under GDPR Articles 32 and 44 (and Schrems II), I need written assurance from Microsoft that biometric and Article 10 data processed through Azure Document Intelligence does not leave the EU/EEA at any point in the request lifecycle — including the model inference layer, not just the customer-deployed resource layer.

If the answers confirm strict in-region processing, we proceed with Azure DI prebuilt-idDocument as our primary passport extractor (replacing direct vendor APIs). If any of the answers indicate cross-region routing, we will need to restrict our use of Document Intelligence to non-Article-9 document types and route passport processing through an alternative on-premises solution — which is a meaningfully worse outcome for us and presumably for Microsoft.

**Timeline**

We have a Cohort 1 pilot launch milestone for early Q3 2026. A 5–10 business day turnaround on this confirmation would let us proceed on schedule.

Happy to schedule a 30-minute call with an Azure CSU compliance engineer if a synchronous discussion is faster than a written response.

Thanks,
Romain Lecomte
Founder, ReloPass
romain_lecomte@hotmail.com

---

## Internal notes (do NOT include in the ticket)

- Microsoft is generally responsive on residency-specific tickets for B/C-severity. Expect first response within 1 business day; full answer typically 5–10 business days.
- If they punt to documentation links, push back: ask for a written statement from a CSU compliance engineer or a Microsoft Account Team Solution Architect specific to prebuilt-idDocument in West Europe. Generic documentation is not enough for a DPIA.
- If they confirm strict in-region: archive the response under `audit/compliance/responses/azure_di_residency_<YYYY-MM-DD>.eml.pdf` and update `audit/AI_TOOLS_AND_FLYWHEEL.md` §1.C2 + `audit/AI_NODE_INVENTORY.md` to remove the "verify in writing" qualifier.
- If they confirm cross-region routing on any leg: switch passport extraction to one of (a) Mistral OCR + custom MRZ parser (per AI-I.2 § ICAO 9303 parser path), (b) Reducto with explicit EU-residency contract, (c) on-premises tesseract + custom CV for MRZ — and update the same docs accordingly.
- The "alternative on-premises" framing at the end of the ticket signals you're prepared to walk; Microsoft sales typically escalates these.
