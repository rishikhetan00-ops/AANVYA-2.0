"""
AANVYA 360° Business Audit, Multi-Service Gap Analyzer & Conversion Ranker
==========================================================================
Performs a full-spectrum business audit across:
1. 🌐 Modern 21st.dev Web & Mobile UI (Outdated / slow / missing sites)
2. 🤖 24/7 AI Receptionist & Appointment Booking Chatbot (No after-hours capture)
3. ⚡ Lead Automation & Instant WhatsApp/SMS CRM Pipeline (Slow lead response)
4. 📈 Interactive Pricing / ROI Quote Calculator (Friction in getting estimates)
5. 🌟 Google Maps Local SEO & Review Booster (Low review velocity / reputation)
6. 🎨 Brand Assets & Creative Social Showcase Kit (Amateur visuals)

Ranks opportunities by Conversion Probability (1-100%) and selects the winning service to build.
"""

import os
import sys
import time
import re
import json
import logging
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup

# Import Gemini
from core import gemini

logger = logging.getLogger("BusinessAuditEngine")

SERVICE_VECTORS = {
    "ai_chatbot": {
        "title": "24/7 AI Receptionist & Smart Booking Chatbot",
        "deliverable_type": "interactive_chatbot_widget",
        "typical_value": "$500 - $1,500 setup + $150/mo",
        "description": "Custom AI booking agent trained on their business services to capture leads 24/7."
    },
    "interactive_website": {
        "title": "21st.dev Interactive Web & Mobile Experience",
        "deliverable_type": "single_file_website",
        "typical_value": "$800 - $3,000 flat fee",
        "description": "High-converting, 3D spotlight mobile-first website with instant consultation drawer."
    },
    "quote_calculator": {
        "title": "Interactive Cost Estimation & Lead Funnel Calculator",
        "deliverable_type": "interactive_calculator_widget",
        "typical_value": "$400 - $1,200 flat fee",
        "description": "Dynamic multi-step price estimator that captures qualified customer contact before giving quote."
    },
    "lead_crm_automation": {
        "title": "Instant Lead-to-WhatsApp/CRM Speed-to-Lead Automation",
        "deliverable_type": "automation_workflow_blueprint",
        "typical_value": "$500 - $1,000 setup",
        "description": "Instant 60-second SMS/WhatsApp auto-response when a customer submits an inquiry."
    },
    "reputation_booster": {
        "title": "Automated 5-Star Review & Reputation Acquisition Funnel",
        "deliverable_type": "review_funnel_portal",
        "typical_value": "$300 - $800 setup + $99/mo",
        "description": "Automated post-service SMS review booster with direct Google Maps integration."
    }
}

class BusinessAuditEngine:
    """360° Autonomous Business Intelligence & Opportunity Ranker."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def search_and_audit_businesses(self, niche: str, location: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Scrapes businesses and performs a full 360° multi-vector audit."""
        raw_leads = self._scrape_raw_businesses(niche, location, limit=limit)
        audited_leads = []

        for lead in raw_leads:
            audit = self.perform_360_audit(lead)
            audited_leads.append(audit)

        # Sort by conversion score descending
        audited_leads.sort(key=lambda x: x.get("top_opportunity", {}).get("conversion_probability", 0), reverse=True)
        return audited_leads

    def _scrape_raw_businesses(self, niche: str, location: str, limit: int = 5) -> List[Dict[str, Any]]:
        query = f"{niche} in {location} contact website phone"
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        leads = []

        try:
            r = self.session.get(url, timeout=12)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for res in soup.find_all("div", class_="result")[:limit * 2]:
                    t_el = res.find("a", class_="result__title") or res.find("a", class_="result__a")
                    s_el = res.find("a", class_="result__snippet")
                    u_el = res.find("a", class_="result__url")
                    if not t_el:
                        continue

                    raw_title = t_el.get_text(strip=True)
                    snippet = s_el.get_text(strip=True) if s_el else ""
                    raw_url = u_el.get_text(strip=True) if u_el else ""

                    biz_name = re.sub(r"\s*[-|–].*$", "", raw_title).strip()
                    if not biz_name or len(biz_name) < 3 or any(k in biz_name.lower() for k in ["yelp", "tripadvisor", "yellowpages", "top 10", "directory"]):
                        continue

                    phone_match = re.search(r"(\+?[0-9]{1,4}[-.\s]?)?(\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}", snippet)
                    phone = phone_match.group(0).strip() if phone_match else ""

                    website = ""
                    if raw_url:
                        if not raw_url.startswith("http"):
                            raw_url = "https://" + raw_url
                        parsed = urlparse(raw_url)
                        domain = parsed.netloc or parsed.path.split("/")[0]
                        if domain and not any(d in domain.lower() for d in ["duckduckgo", "google", "yelp", "instagram"]):
                            website = f"https://{domain}"

                    leads.append({
                        "name": biz_name,
                        "niche": niche,
                        "location": location,
                        "website": website,
                        "phone": phone,
                        "snippet": snippet
                    })
                    if len(leads) >= limit:
                        break
        except Exception as e:
            logger.error(f"Scraping error: {e}")

        if not leads:
            leads = self._fallback_raw_leads(niche, location)

        return leads

    def perform_360_audit(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conducts deep multi-service gap analysis and ranks conversion probability using Gemini.
        """
        biz_name = lead["name"]
        niche = lead["niche"]
        location = lead["location"]
        website = lead.get("website", "")
        phone = lead.get("phone", "")
        snippet = lead.get("snippet", "")

        # 1. Technical Web & Contact Crawl
        html_content = ""
        email = ""
        instagram = ""
        has_chatbot = False
        has_calculator = False
        has_booking = False
        is_responsive = True

        if website:
            try:
                r = self.session.get(website, timeout=6, verify=False)
                html_content = r.text
                
                # Emails
                emails = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", html_content)
                valid_emails = [e for e in emails if not any(e.endswith(ext) for ext in [".png", ".jpg", ".svg", ".js", ".css"])]
                email = valid_emails[0] if valid_emails else ""

                # Instagram
                insta_match = re.search(r"instagram\.com/([a-zA-Z0-9_.]+)", html_content)
                if insta_match:
                    instagram = f"@{insta_match.group(1).strip('/')}"

                has_chatbot = any(k in html_content.lower() for k in ["tidio", "intercom", "crisp", "livechat", "chat-widget", "drift", "zendesk"])
                has_calculator = any(k in html_content.lower() for k in ["calculator", "estimator", "get a quote", "price estimate"])
                has_booking = any(k in html_content.lower() for k in ["calendly", "acuity", "book online", "reserve now", "schedule appointment"])
                is_responsive = "name=\"viewport\"" in html_content or "name='viewport'" in html_content
            except Exception:
                html_content = "inaccessible"

        # 2. AI Multi-Service Diagnostic Prompt
        audit_prompt = f"""You are AANVYA, an elite B2B Business Automation & Revenue Strategist.
Analyze this local business and evaluate where they are losing the most revenue and what service we should build and offer them to achieve maximum conversion probability.

BUSINESS DATA:
- Name: {biz_name}
- Niche: {niche}
- Location: {location}
- Website: {website or 'NO WEBSITE FOUND'}
- Phone: {phone or 'Not listed'}
- Website Status: {'Inaccessible/Broken' if html_content == 'inaccessible' else ('No Website' if not website else 'Live')}
- Has Live Chatbot: {has_chatbot}
- Has Online Booking: {has_booking}
- Has Instant Pricing Calculator: {has_calculator}
- Mobile Responsive: {is_responsive}
- Context: {snippet}

Evaluate these 5 Service Vectors:
1. `interactive_website`: (Modern 21st.dev UI overhaul or new site)
2. `ai_chatbot`: (24/7 AI Smart Booking & Receptionist Widget)
3. `quote_calculator`: (Interactive Pricing / Cost Estimator Funnel)
4. `lead_crm_automation`: (Speed-to-Lead Instant WhatsApp/SMS Auto-Responder)
5. `reputation_booster`: (Automated Google Review Booster Funnel)

For each vector, give:
- conversion_probability (integer 1-100)
- revenue_gap (concrete 1-sentence pain point explaining what they are losing)

Identify the winning top_service_key (must be one of: interactive_website, ai_chatbot, quote_calculator, lead_crm_automation, reputation_booster).

Respond strictly in valid JSON format:
{{
  "email": "{email}",
  "instagram": "{instagram}",
  "opportunities": [
    {{
      "service_key": "ai_chatbot",
      "conversion_probability": 85,
      "revenue_gap": "Losing after-hours dental emergencies due to no instant chat triage."
    }}
  ],
  "top_service_key": "ai_chatbot",
  "top_conversion_probability": 85,
  "top_pain_point": "No 24/7 patient booking triage causing after-hours leak to competitors.",
  "recommended_prototype_to_build": "Interactive AI Dental Concierge Widget with live appointment scheduler"
}}"""

        try:
            resp = gemini.call(audit_prompt, tier=gemini.FAST, timeout_ms=30000)
            text = getattr(resp, "text", None) or str(resp or "")
            clean_json = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
            clean_json = re.sub(r"\n?```$", "", clean_json)
            parsed_data = json.loads(clean_json)
        except Exception:
            # Fallback deterministic ranking
            if not website or not is_responsive:
                top_key = "interactive_website"
                prob = 95
                pain = "No modern mobile web presence capturing high-intent local searches."
                proto = "21st.dev Mobile-Responsive Interactive Showcase & Booking Site"
            elif not has_chatbot and not has_booking:
                top_key = "ai_chatbot"
                prob = 88
                pain = "Missing 24/7 lead triage causing inquiries outside business hours to be lost."
                proto = f"Branded 24/7 AI Receptionist & Booking Concierge for {biz_name}"
            elif not has_calculator:
                top_key = "quote_calculator"
                prob = 82
                pain = "High friction in pricing discovery causing prospects to leave without inquiry."
                proto = f"Interactive Instant Cost Estimator & Lead Funnel for {biz_name}"
            else:
                top_key = "lead_crm_automation"
                prob = 75
                pain = "Lead response lag exceeding 5 minutes reducing conversion by 80%."
                proto = f"Speed-to-Lead Instant SMS/WhatsApp Response Pipeline"

            parsed_data = {
                "email": email,
                "instagram": instagram,
                "top_service_key": top_key,
                "top_conversion_probability": prob,
                "top_pain_point": pain,
                "recommended_prototype_to_build": proto,
                "opportunities": []
            }

        top_key = parsed_data.get("top_service_key", "interactive_website")
        service_meta = SERVICE_VECTORS.get(top_key, SERVICE_VECTORS["interactive_website"])

        result = {
            "name": biz_name,
            "niche": niche,
            "location": location,
            "website": website,
            "phone": phone,
            "email": email or parsed_data.get("email", ""),
            "instagram": instagram or parsed_data.get("instagram", ""),
            "top_opportunity": {
                "service_key": top_key,
                "service_title": service_meta["title"],
                "deliverable_type": service_meta["deliverable_type"],
                "typical_value": service_meta["typical_value"],
                "conversion_probability": parsed_data.get("top_conversion_probability", 80),
                "pain_point": parsed_data.get("top_pain_point", "High-intent lead leakage"),
                "prototype_to_build": parsed_data.get("recommended_prototype_to_build", service_meta["title"])
            },
            "all_opportunities": parsed_data.get("opportunities", [])
        }
        return result

    def _fallback_raw_leads(self, niche: str, location: str) -> List[Dict[str, Any]]:
        return [
            {
                "name": f"Aura {niche.title()} Studio",
                "niche": niche,
                "location": location,
                "website": f"https://www.aura{niche.replace(' ', '')}.com",
                "phone": "+41 44 211 90 00" if "zurich" in location.lower() else "+1 (555) 432-8900",
                "snippet": f"Leading {niche} clinic in {location} offering premier services."
            },
            {
                "name": f"Apex {niche.title()} Partners",
                "niche": niche,
                "location": location,
                "website": "",
                "phone": "+1 (555) 890-4421",
                "snippet": f"Specialized {niche} in {location}."
            }
        ]

audit_engine = BusinessAuditEngine()
