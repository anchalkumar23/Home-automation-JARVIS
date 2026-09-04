# JARVIS AI Operating System Requirements

## Guiding Philosophy

JARVIS is not a chatbot. JARVIS = Memory + Intelligence + Observation + Prediction + Simulation + Automation + Execution.

Its purpose: help make better decisions, detect what's being missed, and turn goals into results — proactively, not just when asked.

**Operating principle:** First understand. Then recommend. Then request authorization. Finally execute. JARVIS should not have unlimited autonomy — consequential actions always require human approval before they happen. (This matches the draft-then-confirm pattern already used for email, calendar writes, and other real-world side effects throughout this build.)

**Build cost-effectively:** prefer free tools and free tiers, avoid unnecessary access requirements or subscriptions that complicate integration. Evaluate a client-suggested app/API before integrating it, and confirm it before assuming it's available.

### The 10 Core Functions

1. **Early Warning System** — continuously monitor authorized information sources and proactively surface things worth knowing (law/regulatory changes, economic shifts, new technology, security risks, service disruptions, events affecting active projects) without waiting to be asked.
2. **Opportunity Engine** — actively look for connections between new technologies, consumer needs, regulatory changes, new companies, emerging markets, patents, search trends, and unsolved problems, and surface specific, evidence-backed opportunities.
3. **Second Brain** — automatically organize everything important into a personal knowledge map (people → projects → documents → decisions → goals → results), so past reasoning can be reconstructed on request ("why did we decide this six months ago?").
4. **Error Detector** — actively stress-test plans rather than simply agreeing; identify problems, flawed assumptions, and more efficient alternatives. An intellectual adversary, not a yes-man.
5. **Decision Simulator** — before a major decision, simulate best-case / likely / worst-case scenarios and identify the variables that could change the outcome.
6. **Global Radar** — detect changes that actually matter and say nothing when nothing matters ("nothing important happened for you today" is a valid, good answer); surface only genuinely relevant events, with an explanation of why they matter to the user's specific projects.
7. **Time Manager** — study how the user spends time, flag tasks that could be automated, and recommend the highest-impact use of upcoming time — not just a calendar readout.
8. **Autonomous Builder** — given a goal, break it into stages (research → design → tools → costs → development → testing → launch), work through stages autonomously, and request authorization before continuing past consequential checkpoints.
9. **Learning System** — track which recommendations worked and which didn't, and use that history to weight future recommendations toward what has actually worked for this user.
10. **"What Am I Forgetting?" Mode** — a standing command that reviews pending projects, important dates, risks, commitments, documents, incomplete decisions, unresolved problems, opportunities, and cross-task dependencies, then reports back concisely.

---

## 1. Core AI Assistant

JARVIS should be an intelligent AI assistant with the following capabilities:

- Communicate naturally with a human-like voice.
- Hold long and intelligent conversations.
- Speak both English and Spanish fluently.
- Switch languages automatically when appropriate.
- Learn from every interaction.
- Remember previous conversations.
- Understand my preferences.
- Call me by my name.
- Explain complex topics clearly.
- Offer suggestions and recommendations when requested.
- Continuously improve over time.

---

## 2. Studio Automation

JARVIS must be able to control my entire studio.

This includes:

- Desktop computers
- Laptops
- Cameras
- Camera settings
- Microphones
- Audio interfaces
- Speakers
- Smart lighting
- Air conditioning
- Smart switches
- Smart plugs
- Monitors
- TVs
- Projectors
- Stream Deck
- NAS storage
- Local servers
- UPS systems
- Smart home devices
- Future hardware

### Voice Example

> "Jarvis, start Podcast Mode."

JARVIS should automatically:

- Turn on lights
- Configure lighting scenes
- Power on cameras
- Launch recording software
- Open project files
- Configure microphones
- Set audio levels
- Start recording
- Display notes on the teleprompter

### Confirmed Hardware & Integration Plan (as of Aug 2026)

**Decision: direct integration, not Home Assistant.** Studio automation is built straight into JARVIS's own codebase — one small tool per device type, talking to each device's own local API/library directly — rather than routing through a separate Home Assistant hub. Trades more code per device for full ownership (matching Section 20's "full source code"/"full ownership" requirement) and a single system to maintain instead of two. See `docs/superpowers/specs/2026-08-19-tv-control-design.md` for the full reasoning and prior-art research behind this call.

**Built:**
- TV control (TCL/Roku, Samsung, LG) — power, volume, mute, app launching, via `samsungtvws`/`PyWebOSTV`/Roku's own local ECP API, with Wake-on-LAN for powering on from fully off. (Increment 7a.)

**Planned, same direct-integration approach, one device type at a time:**
- Smart LED flush mount (pending confirmation of Smart Life / Tuya Smart compatibility — likely via `tinytuya`)
- HIKvision cameras (pending ONVIF confirmation — via `python-onvif`/`hikvisionapi`)
- Fomako camera, if a PTZ model (real pan/tilt/zoom control, not just on/off)
- GVM RGB light, Godox SL6IIBi light — power on/off only, via a smart relay added at the outlet (color/brightness/scenes still require their own app — no API for that part)

**Not automatable / no home-automation angle:**
- Nikon Z30, Sony FX30 (handled via recording software — OBS/vMix — not smart-home control)
- Meta Ray-Ban glasses, PS5 (closed systems)
- XGIMI Titan projector (status pending)
- Tesla (separate integration, own control system, later conversation — not home automation)

Candidate tool: Frigate (open-source NVR with AI object detection) — see also Section 10.

---

## 3. 3D Printing & Jewelry Workshop

JARVIS should manage and monitor:

- Bambu Lab 3D printers
- Phrozen resin printers
- Print jobs
- Material usage
- Printer status
- Error detection
- Print completion alerts
- Maintenance reminders

### For Jewelry Production

JARVIS should:

- Organize design files
- Prepare models for printing
- Generate jewelry concepts using AI
- Create realistic renders
- Track production workflow

---

## 4. AI Content Creation

JARVIS should help create:

- YouTube videos
- Podcasts
- Social media content
- Short-form videos
- Marketing materials
- Blog articles
- Product descriptions
- Presentations
- Scripts

Target platforms: Instagram, Facebook, TikTok, YouTube.

Preferred tool to integrate: CapCut.

---

## 5. AI Video Editing

JARVIS should edit videos automatically.

Features include:

- Automatic rough cuts
- Remove silence
- Remove mistakes
- Multi-camera synchronization
- Audio enhancement
- Noise reduction
- Color correction suggestions
- Subtitle generation
- Translation
- AI dubbing
- Thumbnail generation
- Highlight detection
- Automatic Shorts/Reels generation
- Export in multiple formats
- Upload-ready files

Preferred tools to integrate: CapCut, Whisper, ffmpeg.

---

## 6. Research Assistant

JARVIS should continuously research:

- Artificial Intelligence
- Technology
- Science
- Business
- World news
- Politics
- Government
- Finance
- Stock markets
- Cryptocurrency
- Startups
- Competitors
- Products
- Industry trends

It should summarize findings and cite reliable sources.

### Candidate Data Sources ("Global Radar")

News & media monitoring: GDELT, RSS feeds, Inoreader, Feedly, Media Cloud, Google News, Google Alerts, Reddit.

Crisis & geopolitical monitoring: ACLED, Liveuamap, Crisis24, ReliefWeb, NATO, UN News.

Transport & logistics tracking: ADS-B Exchange, FlightRadar24, OpenSky Network, MarineTraffic, Equasis.

Satellite & environmental monitoring: Copernicus Sentinel, Sentinel Hub, NASA FIRMS, NASA Earthdata, USGS, USGS Earthquakes, NOAA.

Economic & financial data: FRED, BLS, BEA, Federal Reserve, Treasury, World Bank, Trading Economics, SEC EDGAR, FINRA, CBOE, TradingView.

Each of these is a candidate source, not a commitment — evaluate free-tier availability and API access before integrating (per the cost-conscious guiding principle above).

---

## 7. Internet Intelligence

JARVIS should:

- Search the internet
- Compare products
- Read websites
- Read PDFs
- Analyze documents
- Search YouTube
- Read research papers
- Search patents
- Monitor important news

Additional source of interest: Google Maps.

---

## 8. Multiple AI Models

JARVIS should support multiple AI models.

Examples:

- ChatGPT
- Claude
- Gemini
- Grok
- DeepSeek
- Local open-source models (via Ollama)

It should automatically choose the best model depending on the task.

---

## 9. Long-Term Memory

JARVIS should remember:

- Projects
- Studio setup
- Equipment
- Clients
- Business ideas
- Documents
- Notes
- Calendar
- Personal preferences
- Workflows

Candidate technology: pgvector (semantic/vector search over stored memory), for when memory outgrows simple key-value lookup.

---

## 10. Computer Vision

Using cameras, JARVIS should:

- Recognize authorized people
- Detect movement
- Read documents
- Read screens
- Count objects
- Monitor 3D printers
- Detect equipment problems
- Observe studio activity

Candidate tool: Frigate (open-source NVR with AI object detection) — likely paired with the HIKvision cameras from Section 2.

---

## 11. Holographic Avatar

I want a visual AI avatar.

The avatar should:

- Speak naturally
- Lip-sync accurately
- Blink
- Display facial expressions
- Make eye contact
- React emotionally
- Be displayed using multiple projectors or large displays to create an immersive presence

### 3D Interactive Globe Interface (frontend vision, deferred)

A future frontend redesign concept the client has described, not yet scheduled for implementation:

- A highly realistic, interactive 3D globe as the main interface, showing all countries.
- Each country should be clickable/touchable to focus conversation/research on that country.
- A cyber-human JARVIS avatar integrated naturally into the interface — present but not dominating the screen.
- Overall aesthetic: futuristic, realistic, clean, high-end, uncluttered, and fully functional/interactive, not just decorative.
- Reference mockup images were provided by the client directly (not stored in this repo) — consult them with the client when this is scheduled for design work.

---

## 12. Mobile Companion

JARVIS should also work on:

- iPhone
- iPad
- Laptop

It should synchronize all conversations and data automatically.

I want to take JARVIS with me wherever I go.

Candidate technology: Tailscale (secure remote access / mesh VPN) — likely also the transport for Section 13's remote control.

---

## 13. Remote Control

JARVIS should allow me to remotely:

- Monitor cameras
- Control lights
- Control computers
- Check printer status
- Restart devices
- Start recordings
- Monitor the studio

---

## 14. Productivity Assistant

JARVIS should manage:

- Calendar
- Meetings
- Reminders
- Email assistance
- Task management
- Notes
- Daily planning
- Priorities

---

## 15. Business Intelligence

JARVIS should assist with:

- Business strategy
- Financial analysis
- Market research
- Competitor analysis
- Sales insights
- Marketing campaigns
- Customer analytics
- Business reports

Candidate data sources: TradingView, financial market APIs, Zillow, Redfin (real estate research).

---

## 16. AI Software Development Assistant

One of the most important goals is for JARVIS to help me build software.

It should assist with:

- Writing code
- Debugging
- Creating desktop applications
- Building web applications
- Designing APIs
- Creating AI-powered software
- Explaining code
- Reviewing code
- Suggesting improvements
- Building automation tools
- Creating custom business software

Preferred toolchain: Python, VS Code, Git, GitHub, Open Code.

---

## 17. AI Engineering Assistant

JARVIS should help me invent and build new technology.

Examples:

- Design electronic systems
- Assist with Raspberry Pi projects
- Assist with robotics
- Help develop AI-powered hardware
- Generate engineering ideas
- Create technical documentation
- Simulate concepts before building

---

## 18. Security

The system should include:

- Authentication
- User permissions
- Encrypted communication
- Automatic backups
- Activity logs
- Error reporting
- Recovery tools

---

## 19. Scalability

The system should be modular.

Future integrations may include:

- Robots
- Robotic arms
- Drones
- Smart glasses
- Wearable devices
- Additional cameras
- Sensors
- Industrial equipment

Candidate infrastructure: Docker (containerized deployment), n8n (workflow automation).

---

## 20. System Requirements

The developer must provide:

- Full source code
- Full ownership of the project
- Complete documentation
- Installation guide
- API documentation
- Expandable architecture
- Cross-platform compatibility
- Local server support
- Cloud deployment support
- Mobile synchronization
- Web dashboard
- Update mechanism

---

# Final Goal

The long-term vision is to create an AI operating system similar in concept to **"JARVIS"** from science fiction—not by copying fictional technology, but by building a practical, expandable assistant that becomes the intelligent control center for my studio, my business, my software development, and my daily life.

This project should be built so it can continue evolving for many years as new AI technologies become available.
