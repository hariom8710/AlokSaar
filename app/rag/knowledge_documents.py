"""
Seed knowledge documents for the RAG knowledge base (Knowledge Sources on
the poster: Drug Information, Manufacturer Info, Government Rules,
Compliance Policies, Pharmacy SOPs, Medical Guidelines, Internal Documents).

In production these would be ingested from real drug databases, government
regulation PDFs, and the pharmacy's own SOP documents. This seed set is
illustrative content to make the RAG pipeline demonstrably functional.
"""

KNOWLEDGE_DOCUMENTS = [
    {
        "id": "drug_info_paracetamol",
        "category": "drug_information",
        "text": (
            "Paracetamol (Acetaminophen) 650mg: Common analgesic and antipyretic used for "
            "fever and mild-to-moderate pain. Standard adult dose is 500-1000mg every 4-6 "
            "hours, max 4g/day. Fast-moving OTC item with year-round demand, spikes during "
            "flu season (monsoon and winter months in North India). Store below 25°C, "
            "protect from moisture. Shelf life typically 24-36 months from manufacture."
        ),
    },
    {
        "id": "drug_info_amoxicillin",
        "category": "drug_information",
        "text": (
            "Amoxicillin 500mg: Broad-spectrum penicillin antibiotic, requires a valid "
            "prescription under Schedule H. Common course length 5-7 days. Sensitive to "
            "moisture and heat; shorter shelf life than most OTC items (typically 24 "
            "months). Demand correlates with respiratory and bacterial infection season."
        ),
    },
    {
        "id": "drug_info_ors",
        "category": "drug_information",
        "text": (
            "ORS (Oral Rehydration Salts): Used to treat dehydration, especially from "
            "diarrhea and heat exposure. Demand rises sharply in summer months (April-June) "
            "and during gastrointestinal illness outbreaks. Low cost, high volume item; "
            "stock-outs directly translate to lost footfall since customers often buy other "
            "items on the same visit."
        ),
    },
    {
        "id": "compliance_schedule_h",
        "category": "compliance_policy",
        "text": (
            "Schedule H and H1 drugs (including most antibiotics, and certain sedatives) "
            "cannot be sold without a valid prescription from a registered medical "
            "practitioner. Pharmacies must maintain a register of Schedule H1 sales "
            "including patient name, prescriber details, and quantity dispensed, retained "
            "for at least 3 years. Violations can result in license suspension."
        ),
    },
    {
        "id": "compliance_expiry_disposal",
        "category": "compliance_policy",
        "text": (
            "Expired medicines must not be sold or dispensed under any circumstances. "
            "Pharmacies should segregate expired stock immediately upon identification, "
            "maintain a disposal/return log, and follow state pollution control board "
            "guidelines for pharmaceutical waste disposal or return expired stock to the "
            "distributor for credit where the purchase agreement allows it."
        ),
    },
    {
        "id": "sop_expiry_management",
        "category": "sop",
        "text": (
            "Standard Operating Procedure — Expiry Management: (1) Conduct a physical "
            "expiry audit monthly. (2) Flag any batch expiring within 90 days as 'at risk'. "
            "(3) For at-risk high-value batches, negotiate return-to-distributor first. "
            "(4) For non-returnable at-risk stock, apply a graduated discount (10% at 90 "
            "days, 25% at 45 days, 40% at 15 days) to clear stock before expiry. (5) Items "
            "within 15 days of expiry and unsold should be pulled from active shelf stock."
        ),
    },
    {
        "id": "sop_reorder_policy",
        "category": "sop",
        "text": (
            "Standard Operating Procedure — Reordering: Reorder level for each medicine "
            "should reflect its average daily sales multiplied by supplier lead time plus "
            "a safety buffer (typically 3-5 days). Fast-moving items (analgesics, ORS, "
            "common antibiotics) should carry a higher safety buffer given the higher cost "
            "of a stock-out. Slow-moving or seasonal items should be ordered in smaller, "
            "more frequent batches to reduce dead stock risk."
        ),
    },
    {
        "id": "manufacturer_info_general",
        "category": "manufacturer_info",
        "text": (
            "Manufacturer-authorized distributors typically offer better margins on bulk "
            "orders (50+ units) and provide 30-45 day payment credit terms for pharmacies "
            "with a consistent order history. Distributor reliability should be tracked by "
            "on-time delivery rate; pharmacies should maintain at least two supplier "
            "relationships per high-volume category to avoid single-supplier dependency."
        ),
    },
    {
        "id": "gov_rules_gst_pharmacy",
        "category": "government_rules",
        "text": (
            "Pharmacies in India are generally required to be GST-registered if annual "
            "turnover exceeds the applicable threshold. Most medicines attract 5% or 12% "
            "GST depending on classification; life-saving drugs may be exempt or taxed at "
            "a lower rate. Accurate HSN code classification per medicine is required for "
            "GST filing and is often a source of compliance errors for small pharmacies."
        ),
    },
    {
        "id": "medical_guidelines_antibiotic_stewardship",
        "category": "medical_guidelines",
        "text": (
            "Antibiotic stewardship guidelines recommend pharmacies avoid dispensing "
            "antibiotics without prescription even for seemingly minor complaints, given "
            "rising antimicrobial resistance concerns. Pharmacists should counsel patients "
            "on completing the full prescribed course rather than stopping once symptoms "
            "improve, and should flag repeat short-course purchases for pharmacist review."
        ),
    },
    {
        "id": "internal_doc_seasonal_demand",
        "category": "internal_documents",
        "text": (
            "Internal seasonal demand notes: Cough and cold remedies, fever medication, "
            "and vitamin C see elevated demand during the monsoon and early winter months. "
            "ORS and antidiarrheal medication demand rises in peak summer. Historically, "
            "under-stocking fever medication during seasonal transitions has been a "
            "recurring cause of lost sales; proactive pre-season stocking is recommended."
        ),
    },
    {
        "id": "internal_doc_vitamin_overstock",
        "category": "internal_documents",
        "text": (
            "Internal note: Vitamin and supplement categories (Vitamin C, Calcium, "
            "multivitamins) have historically been over-ordered relative to actual demand, "
            "leading to dead stock. Recommendation is to order these categories in smaller "
            "batches based on trailing 30-day sales rather than round-number bulk orders."
        ),
    },
]
