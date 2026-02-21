Self-Improving Content Intelligence Platform
(Working title — rename to taste)

REFINED CONCEPT
A company onboards to the platform, teaches it who they are and what they want to achieve. SIGNAL then deploys a multi-agent system that monitors prediction market data from Polymarket as a real-time leading indicator of what the world is about to care about. It generates campaign options, recommends distribution channels, posts content, monitors performance, and — critically — feeds all of that back into itself to get smarter over time. Every campaign makes the next one better. The system learns across all three dimensions simultaneously.
This is not a content scheduler. It's a living marketing intelligence system.

THE THREE SELF-IMPROVING LOOPS (go big, as requested)
This is the core of your hackathon argument. You need to be able to draw this on a whiteboard in 30 seconds.
Loop 1 — Campaign Performance Feedback
Agent posts content → tracks engagement metrics → scores which campaign styles, tones, hooks, and formats actually drove results → updates the content generation agent's prompt weighting for that company. Over time, a fintech company's content agent sounds nothing like a gaming company's, because it learned from actual outcomes not just onboarding preferences.
Loop 2 — Cross-Company Style Learning (Federated)
Anonymized style patterns from all companies on the platform feed into a shared knowledge layer. If aggressive short-form copy consistently outperforms long-form across 50 companies when a Polymarket topic hits 80%+ volume, every company's agent gets smarter about that correlation — without sharing any proprietary content. Think of it as agents teaching each other through aggregate signal.
Loop 3 — Polymarket Signal Calibration
The system tracks which Polymarket signals it acted on, what it generated in response, and whether that content actually captured engagement. Over time, it learns which probability thresholds, which categories (politics vs. crypto vs. macro), and which volume velocity patterns are actually predictive for content virality — versus noise. It stops chasing every spike and gets better at knowing which trends are worth riding for which company types.
These three loops together are what make this genuinely self-improving — not just a tool, but a compounding system.

SPONSOR INTEGRATION STRATEGY
This is where you pick up prize money. Here's how to architect specifically for each sponsor:
Airia ($1,000 prize) — This is your entire agent orchestration backbone. Airia is an enterprise AI platform with a no-code workflow builder, multi-model routing, and secure integrations. Your multi-agent pipeline — the brand understanding agent, the Polymarket trend agent, the content generation agent, the distribution routing agent, and the feedback loop agent — all get built and orchestrated through Airia. This is a natural fit because Airia literally does multi-agent workflow management. You're not hacking it in; you're using it as intended at enterprise scale. Your pitch to Airia's judges: "We used Airia as the orchestration layer for a five-agent self-improving system. Every agent is a workflow in Airia, and the feedback loop updates those workflows dynamically."
Lightdash ($1,000 prize) — This is your analytics and observability dashboard, and it's a perfect fit. Every piece of your system generates data: Polymarket signal history, campaign performance metrics, content quality scores, agent improvement over time, channel performance by content type. Lightdash is an open-source AI-native BI platform that sits on top of your data warehouse. You build a Lightdash dashboard that shows the self-improvement happening in real-time: campaign performance trends, agent learning curves, which Polymarket signals predicted engagement, and which channels are winning. This makes the abstract concept of "self-improving agents" visually concrete to judges. You can literally show a graph of the system getting smarter. That is a powerful demo moment. Pitch to Lightdash: "We built the observability layer for our self-improving agent system in Lightdash, turning abstract ML feedback loops into business-readable intelligence."
Modulate ($1,000 prize) — This is the hardest integration, and you need to be creative but honest. Modulate is a voice intelligence and content moderation API. Here's the angle that works: when your system generates content, it needs to ensure brand safety before it posts. You use Modulate's voice/content intelligence layer to audit generated content for tone risk, brand-unsafe language, and potential community harm before it goes out. You can also add a feature where companies can record a voice brief — "here's what our brand sounds like, here's what we want this campaign to feel like" — and Modulate processes that audio to extract brand voice signals that feed back to the content agent. That's a genuine and defensible use of their API, not a stretch. Pitch to Modulate: "We integrated Modulate's voice intelligence to create a pre-publication brand safety layer and voice-to-brief input method for the content generation agent."

ARCHITECTURE (what you're actually building)
Five agents, each with a clear job:
Agent 1 — Brand Intake Agent takes the company through onboarding. Industry, tone of voice, target audience, campaign goals, competitor brands to avoid sounding like, content history if they have it. Stores this as a company profile. Built on Airia.
Agent 2 — Trend Intelligence Agent continuously polls Polymarket's Gamma API for trending markets, filtering by volume velocity (not just raw volume — the rate of change matters more for content timing), probability momentum, and category relevance to the company profile. It surfaces 3–5 signals per cycle. This is your unique differentiator. Be specific in the demo: "At 9 AM this morning, Polymarket showed the 'Fed rate cut in March' market spiking from 34% to 61% in 48 hours on $2.1M volume. Our system flagged this as a high-confidence content opportunity for our fintech client."
Agent 3 — Campaign Generation Agent takes the brand profile + Polymarket signals and generates 3–5 distinct campaign concepts. Each concept includes headline, body copy, visual direction notes, a confidence score, and a channel recommendation with reasoning. Uses an LLM with the brand profile embedded in the system prompt. This agent's prompt templates are updated by Loop 1 as performance data comes in.
Agent 4 — Distribution Routing Agent takes the campaign concepts and scores them for channel fit. Short punchy takes → Twitter/X. Visual-heavy narratives → Instagram. Thought leadership → LinkedIn. It doesn't just say "this is for Twitter" — it explains why: post length, engagement format, audience overlap with the Polymarket topic, and time-of-day posting recommendations. This is the channel intelligence layer.
Agent 5 — Feedback Loop Agent is the meta-agent that closes all three loops. It monitors campaign performance after posting, scores outcomes, updates the content agent's strategy weights, feeds anonymized patterns to the shared knowledge layer, and recalibrates the Polymarket signal-to-engagement correlation model. This is the "self-improving" engine that justifies the entire hackathon theme.

DEMO FLOW FOR PRESENTATION
The best hackathon presentations are live demos with a tight narrative. Here's the exact flow:
Minute 0–1: The Hook
Open with a Polymarket screenshot showing a market that just spiked — something concrete and current. Say: "This morning, prediction markets moved $4 million on [real trending topic]. Most companies won't know this is relevant to their content strategy until it's already trending on Twitter — three days later. We fix that."
Minute 1–2: Onboarding in 30 seconds
Live demo of the company onboarding. Type in a fictional company name, industry, and goal. Show the brand profile being created. Keep it fast.
Minute 2–3: Trend Signal in Action
Pull up the live Polymarket API feed. Show the trend agent surfacing the top signal and explaining why it's relevant to this company specifically. This is your technical credibility moment.
Minute 3–4: Campaign Generation
Show three campaign concepts being generated. Read one of them out loud. It should sound good. This is where the audience leans in.
Minute 4–5: Channel Routing + Lightdash Dashboard
Show the distribution routing recommendation, then flip to the Lightdash dashboard. Show performance history, agent learning curves, and the Polymarket calibration graph. This makes the self-improvement real and visual.
Minute 5–6: The Three Loops Explained
One slide, one minute, draw the three feedback loops. This is the "so what" moment that ties everything to the hackathon theme.
Minute 6–7: Sponsor callouts + prize pitch
Explicitly name how you used Airia, Lightdash, and Modulate. Judges from those companies are in the room. Make them feel seen.
