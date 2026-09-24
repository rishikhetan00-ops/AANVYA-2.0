"""
AANVYA Multi-Service Pitch & Sales Outreach Generator
=====================================================
Generates hyper-personalized, value-first outreach packages across Email,
WhatsApp, and Instagram/LinkedIn DM tailored to the specific winning service vector.
"""

from typing import Dict, Any

class PitchGenerator:
    """Generates personalized B2B outreach pitches based on the audited top service vector."""

    @staticmethod
    def generate_pitch_package(lead: Dict[str, Any], demo_url: str = "") -> Dict[str, str]:
        biz_name = lead.get("name", "there")
        niche = lead.get("niche", "business")
        loc = lead.get("location", "your city")
        top_op = lead.get("top_opportunity", {})
        
        service_key = top_op.get("service_key", "interactive_website")
        service_title = top_op.get("service_title", "Custom 2026 Solution")
        pain_point = top_op.get("pain_point", "Missed after-hours inquiries")
        proto_name = top_op.get("prototype_to_build", "Custom Interactive Prototype")
        conv_prob = top_op.get("conversion_probability", 85)

        # ── 1. Service-Specific Email Copy ──────────────────────────────────
        if service_key == "ai_chatbot":
            subject = f"Quick concept: 24/7 AI Receptionist & Booking Concierge for {biz_name}"
            email_body = f"""Hi {biz_name} Team,

I came across your practice in {loc} while researching top-rated {niche} in the area. 

I noticed an immediate revenue opportunity: when patients or clients visit outside standard working hours, there is currently no instant way for them to triage inquiries or secure appointment slots, causing high-intent leads to bounce to competitors ({pain_point.lower()}).

Instead of just pitching an idea, our AI engineering studio built a working interactive 24/7 AI Booking Concierge specifically customized for {biz_name}:
👉 Test Live Concierge Demo: {demo_url or '[LIVE_PROTOTYPE_LINK]'}

What it does right out of the box:
• Instantly answers patient questions 24/7 based on your exact services
• Qualifies patient intent and schedules appointments directly into your calendar
• Connects directly to WhatsApp and email for immediate notifications

If you find this valuable for {biz_name}, we can configure and deploy it to your website in under 24 hours.

Would you be open to a 5-minute chat this Thursday at 11 AM?

Best regards,
Rishi Khetan
Founder, AANVYA Automation Studio"""

            whatsapp_pitch = f"""Hey {biz_name} team! 👋 Came across your {niche} in {loc}. Noticed you might be losing after-hours appointment inquiries. We actually built a working 24/7 AI Booking Concierge prototype for {biz_name} so you can test it live: {demo_url or '[DEMO_LINK]'} — Would love to get your thoughts!"""

        elif service_key == "quote_calculator":
            subject = f"Interactive Instant Cost Estimator prototype for {biz_name}"
            email_body = f"""Hi {biz_name} Team,

I was reviewing {biz_name}'s services in {loc} and noticed that potential clients often face friction when trying to estimate project costs before reaching out ({pain_point.lower()}).

To help you convert 3x more visitors into pre-qualified leads, our studio built an interactive Instant Project & Cost Estimator tailored specifically for {biz_name}:
👉 Test Live Estimator: {demo_url or '[LIVE_PROTOTYPE_LINK]'}

Features:
• Step-by-step interactive sliders for project scope and add-on selection
• Automatically captures prospect name, phone & email before revealing estimate
• Pushes pre-qualified lead details directly to your phone

We can embed this directly on your site for a straightforward flat fee. Open to a quick 5-minute chat this week?

Best regards,
Rishi Khetan
Founder, AANVYA Automation Studio"""

            whatsapp_pitch = f"""Hey {biz_name} team! 👋 Built an interactive Instant Cost Estimator prototype for {biz_name} to help capture more pre-qualified leads: {demo_url or '[DEMO_LINK]'} — Take a look and let me know what you think! 🚀"""

        else: # Default: interactive_website
            subject = f"Quick question regarding {biz_name}'s mobile web presence / 2026 prototype"
            email_body = f"""Hi {biz_name} Team,

I came across your business in {loc} while researching premier {niche} in the area. 

I noticed your current web presence has a significant modernization opportunity ({pain_point.lower()}), which can impact mobile conversion rates.

Our AI design lab put together a bespoke 2026 interactive single-file prototype tailored specifically for {biz_name}:
👉 Preview Demo: {demo_url or '[LIVE_PROTOTYPE_LINK]'}

Highlights:
• 100% mobile-first responsive architecture with smooth 3D interactive physics
• Built-in consultation & lead capture drawer
• Lightning-fast sub-second load performance

If you love the direction, we can deploy this to your domain for a flat setup fee. Would you be open to a brief chat this Thursday?

Best regards,
Rishi Khetan
Founder, AANVYA Automation Studio"""

            whatsapp_pitch = f"""Hey {biz_name} team! 👋 Came across your {niche} in {loc}. Our design lab built a custom 2026 interactive prototype specifically for {biz_name}: {demo_url or '[DEMO_LINK]'} — Would love to hear your feedback!"""

        dm_pitch = f"""Hey {biz_name}! Love what you guys are doing in {loc}. We built a custom interactive prototype for {biz_name} ({proto_name}): {demo_url or '[DEMO_LINK]'}. Check it out when you have a moment! 🚀"""

        return {
            "service_key": service_key,
            "service_title": service_title,
            "conversion_probability": conv_prob,
            "pain_point": pain_point,
            "email_subject": subject,
            "email_body": email_body,
            "whatsapp_pitch": whatsapp_pitch,
            "dm_pitch": dm_pitch
        }

pitch_generator = PitchGenerator()
