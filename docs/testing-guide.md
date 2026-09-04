# Ultimate JARVIS — Manual Testing Guide

This is a living checklist of how to manually verify every feature in the app via the browser. Updated every time a new feature is added.

## Core Chat & Memory

JARVIS remembers facts about the user across sessions and proactively uses them, and replies bilingually (English/Spanish) in both text and voice.

1. Type `Remember that my name is <your name>`. Reload the page (new session). Type `Hello`. Expected: JARVIS greets you by name without being asked to recall it.
2. Type a preference without the word "remember", e.g. `I really love hiking on weekends`. Then type `What do you know about me?`. Expected: the hiking preference is included in the answer, and the `tools_used` metadata under the reply shows a `✓ save_memory` call happened on the first message.
3. Type a full message in Spanish, e.g. `Hola, ¿qué hora es en Madrid?`. Expected: the reply text is in Spanish, and if the browser has a Spanish voice installed (check the voice dropdown in the header for any `es-*` entries), it's spoken in that voice.
4. Immediately send an English message, e.g. `Thanks, what about in New York?`. Expected: the reply switches back to English text and (if applicable) the English voice.

## Voice Input (bilingual, silence auto-stop, wake word)

Voice input records via the microphone, transcribes through Groq Whisper (supporting English and Spanish), auto-stops after a period of silence, and can be triggered hands-free with the wake word "Jarvis."

1. Click the mic button, allow microphone access, speak a short English command (e.g. "What time is it?"), click the mic again to stop. Expected: correctly transcribed and answered.
2. Click the mic, speak a command in Spanish (e.g. "¿Qué hora es?"), click again to stop. Expected: correctly transcribed in Spanish — this is the core capability the old browser recognizer could not provide.
3. Click the mic, speak a short phrase, then go quiet and wait. Expected: recording stops on its own after about 5 seconds of silence, and the transcribed text is still sent and answered correctly.
4. Click the mic, speak, and click again to stop before 5 seconds of silence has passed. Expected: stops immediately, transcribes, sends — same as manual stop always worked.
5. While recording, watch the central bar visualizer. Expected: it visibly reacts to actual voice volume (louder/more active when speaking, flatter when quiet), not a generic animation unrelated to what's being said.
6. Click "Wake" in the header, say "Jarvis" out loud, then speak a command in either language once it starts listening. Expected: wake-word detection triggers, hands off correctly into recording, and transcribes. If wake word fails to activate or later fails, a clear error message appears in the comms log (not a silent revert to inactive with no explanation).
7. In the browser's site settings, block microphone access for `localhost:3000`, reload, then click the mic button. Expected: a clear inline message appears in the comms log (not a silent failure or console-only error); typing still works normally.
8. Press `Ctrl+J`, speak a short command, press `Ctrl+J` again to stop. Expected: same recording/transcription flow as the mic button.
9. (Optional) Open the app in a non-Chromium browser (e.g. Firefox). Expected: the mic button is enabled and voice input still works; the "Wake" button should not appear (or be disabled), since wake-word detection depends on Chromium's `SpeechRecognition`.

## Gmail — Connect & Send

JARVIS can draft an email and send it through the user's own Gmail account via a one-time OAuth connection; sending is always a user-clicked action, never automatic.

1. Click "Connect Gmail" in the header. Expected: a new tab opens Google's real consent screen; after approving, the callback page shows "Gmail connected as <your email>." Return to the JARVIS tab and reload — the header button should now show "Gmail" (connected state).
2. Type something like "Write an email to yourself about testing JARVIS." Expected: a draft card appears with an editable recipient field and editable Subject/Body. Enter your own email address, click "Send via Gmail." Expected: a "Sending…" state briefly, then a comms-log confirmation — and the email actually arrives in the recipient's inbox shortly after.
3. On a new email draft, click "Open in Mail App" instead. Expected: opens your default mail client with the draft prefilled.
4. Try sending with an obviously invalid recipient (e.g. `not-an-email`). Expected: a clear error message in the comms log, not a silent failure or raw stack trace.

## Calendar — Read

JARVIS can answer questions about the user's upcoming Google Calendar events (read-only), using the same connected Google account as Gmail.

1. Click the "Gmail"/"Connect Gmail" header button (reconnect if needed). Expected: Google's consent screen now lists both mail-sending and calendar-viewing permissions. Approve it; hovering the header button afterward shows a tooltip mentioning both Mail and Calendar.
2. Type or say "What's on my calendar this week?" Expected: JARVIS lists real upcoming events from the connected Google account (create a test event in Google Calendar first if it's currently empty).
3. Ask "What's on my calendar today?" or "in the next 3 days." Expected: the narrower date range is respected in the results.
4. Send a quick test email via "Send via Gmail" again. Expected: still works after the scope-widening reconnect.
5. (Optional) Revoke calendar access at `https://myaccount.google.com/permissions` (find the JARVIS app, remove access), then ask "what's on my calendar" without reconnecting first. Expected: a clear "please reconnect to grant calendar permission" message, not a raw error or crash. Reconnect afterward to restore normal function.

## Calendar — Write (create, edit, delete)

JARVIS can propose creating, editing, or deleting calendar events — always as a draft/confirmation the user approves via a UI button, never an autonomous action.

1. Ask "Schedule a team sync tomorrow at 3pm for 30 minutes." Expected: a "New Calendar Event" draft card appears with the title and correctly resolved date/time pre-filled. Edit a field if you like, then click "Create Event." Expected: a confirmation message in the comms log, and the event actually appears on the real Google Calendar.
2. Schedule another event and include an attendee's email address you can check. Confirm and click "Create Event." Expected: the event is created and the attendee actually receives a real Google Calendar invitation email.
3. Ask "What's on my calendar this week?", then ask to reschedule or edit one of the listed events. Expected: the draft card appears in edit mode ("Edit Calendar Event" / "Save Changes"), pre-filled with that event's existing details. Change something and save — confirm the real event is updated, not duplicated.
4. Ask to delete an event. Expected: a "Delete Event?" confirmation appears (not a full draft card) showing the event's title/time. Click "Delete Event." Expected: a confirmation message, and the event is actually removed from the real calendar.
5. Trigger another delete confirmation and click "Cancel" instead. Expected: a "Cancelled" message, and the event is still present on the real calendar afterward.
6. Quickly re-verify a Gmail send and a calendar read still work, confirming nothing regressed.

## Tasks & Reminders

Tasks can have a due date and priority, can be marked done or deleted, and JARVIS can send an opt-in browser notification when a task's due time arrives (while the tab is open).

1. Ask "Remind me to call the dentist tomorrow at 10am, high priority." Expected: the relative date resolves correctly. Ask "what are my tasks" to confirm it saved with the right due date and priority.
2. Ask to mark that task done, and separately add and delete a different task. Expected: both actually change stored state — verify via "show my tasks" (completed/deleted tasks disappear or show as done accordingly).
3. Add a task with a due time a couple of minutes in the future. Click "Reminders" in the header — the browser should prompt for notification permission; allow it. Wait for the due time. Expected: a real browser notification appears while the tab is open.
4. Confirm a task with no due date never triggers a notification, and a task already marked done doesn't either.
5. Click "Reminders" again to turn it off. Expected: no further notifications, even past a task's due time.
6. Quickly re-verify an earlier capability (e.g. send a test email or ask about the calendar) to confirm this increment didn't break anything prior.

## Web Search (Tavily)

JARVIS answers factual and current-events questions using real, ranked web search results (via Tavily) instead of the old DuckDuckGo instant-answer lookup, which frequently returned nothing for anything beyond simple facts.

1. First-time setup: sign up free at tavily.com (no card required), copy the API key (starts with `tvly-`), and paste it into `TAVILY_API_KEY=` in `backend\.env`. Restart the backend.
2. Ask something needing real ranked results, e.g. "Search for the latest developments in solid-state batteries." Expected: relevant results with real titles/URLs/snippets and a coherent summarized answer — not an empty or generic response (this is the case that used to fail with DuckDuckGo).
3. Below the spoken/text answer, expect a "Sources" list with clickable links (title + domain, opening in a new tab) built from the same search results — the answer text itself stays clean of raw URLs since it's also read aloud by TTS.
4. Ask a simple factual query, e.g. "Search what is the capital of France." Expected: still answers correctly, with sources shown.
5. Temporarily blank out or break `TAVILY_API_KEY` in `backend\.env`, restart the backend, and ask a search query again. Expected: a clear "not configured" or "search failed" message, not a crash or silent failure, and no empty "Sources" block. Restore the real key and restart the backend afterward.

## Webpage & PDF Reading

JARVIS can fetch a specific webpage or PDF you link to and read its actual content, for summarizing or answering questions — only when you explicitly ask it to read/summarize a link, not automatically whenever a URL appears.

1. Ask something like "Summarize this article: `<a real article URL>`." Expected: the reply reflects that specific article's actual content, and a "Read: `domain.com`" link appears under the reply, opening the same URL in a new tab.
2. Ask something like "What does this PDF say about X: `<a real, short, public PDF URL>`?" Expected: a specific answer drawn from the PDF's actual text.
3. Ask JARVIS to read a very long page, then ask "did you read the whole thing?" Expected: it acknowledges it only saw the beginning, not a false claim of full coverage.
4. Ask JARVIS to read a YouTube video URL or a direct image URL. Expected: a clear "can't read this type of content" message, not garbled text.
5. Ask JARVIS to read an unreachable or typo'd URL. Expected: a clear error message, not a crash.
6. Quickly re-verify plain web search (e.g. "search for...") still works normally.

## News Monitoring

JARVIS gives a spoken summary of what's happening on a topic (or in general), backed by real, recent, cited sources — not a bare list of headline titles.

1. Ask "What's the latest news on `<a real, currently active topic>`?" Expected: a real summary of what's happening, spoken as natural sentences, with a "Sources" link list underneath showing real, recent articles.
2. Ask "What's happening in the news today?" with no topic. Expected: still works, returns current general news summarized the same way.
3. Check the reply text — it should read as flowing spoken sentences, not a recited list or bullet points.
4. Temporarily blank out or break `TAVILY_API_KEY` in `backend\.env`, restart the backend, and ask for news again. Expected: a clear error/not-configured message, not a crash. Restore the real key and restart the backend afterward.
5. Quickly re-verify web search (3a) and reading a webpage/PDF (3b) still work unaffected.

## YouTube, Paper & Patent Search

JARVIS can search YouTube videos, academic research papers, and patents on a topic, each returning real results (not guesses) with a Sources link list, spoken as a short summary rather than a recited list.

1. First-time setup for YouTube: in the same Google Cloud project used for Gmail/Calendar, enable "YouTube Data API v3" and create a plain API key (Credentials → Create Credentials → API Key, not OAuth). Paste it into `YOUTUBE_API_KEY=` in `backend\.env` and restart the backend.
2. Ask "Find some YouTube videos about `<a real topic>`." Expected: real video titles/channels, spoken as a short summary, with a Sources list of clickable YouTube links.
3. Ask "Find research papers about `<a real topic>`." Expected: real paper titles/authors/years, spoken as a short summary, with a Sources list of clickable links. No setup needed — this one works out of the box.
4. Ask "Search for patents on `<a real topic>`." Expected: plausible patent-related results (via a Google Patents-scoped search), with a Sources list. No new setup needed — reuses the Tavily key from web search.
5. Temporarily blank out or break `YOUTUBE_API_KEY` in `backend\.env`, restart the backend, and ask for a YouTube search again. Expected: a clear "not configured" message, not a crash. Restore the real key and restart the backend afterward.
6. Quickly re-verify web search, news, and reading a webpage/PDF (3a-3c) still work unaffected.

## Market Data (Stocks/Forex/Crypto)

JARVIS can look up a real-time price quote for a stock, forex pair, or cryptocurrency — one tool covering all three via Finnhub.

1. First-time setup: sign up free at finnhub.io (no card required), copy the API key, and paste it into `FINNHUB_API_KEY=` in `backend\.env`. Restart the backend.
2. Ask "What's Apple stock trading at?" Expected: a real, current price with change/percent spoken naturally, no bullets or lists.
3. Ask "What's the EUR to USD rate?" and "What's Bitcoin trading at?" Expected: real data comes back. If either gives a "couldn't find that" response when it shouldn't, that's worth flagging — Finnhub's free-tier support for forex/crypto through this endpoint hadn't been confirmed before building this.
4. Ask for a nonsense symbol (e.g. "what's XYZQQQ trading at"). Expected: a clear "couldn't find that" message, not a fabricated zero price.
5. Temporarily blank out or break `FINNHUB_API_KEY` in `backend\.env`, restart the backend, and ask for a quote again. Expected: a clear "not configured" message, not a crash. Restore the real key and restart the backend afterward.
6. Quickly re-verify web search or news still works unaffected.

## Company/Competitor Research

JARVIS researches a company or competitor thoroughly — multiple search angles plus reading the most relevant source — instead of answering from a single shallow search. No new setup needed; this reuses web search and page reading already configured.

1. Ask "Research `<a real, findable company>` for me." Expected: the reply covers more than one angle — what they do, something recent, and (if findable) funding/market position — not a one-line shallow answer.
2. Check the Sources list under that reply — it should include links from more than one distinct search, not just whatever a single search happened to return.
3. Ask about a company/topic where a specific angle (e.g. funding) genuinely isn't findable. Expected: JARVIS says it couldn't find that piece, not a fabricated number.
4. Confirm the reply reads as natural spoken sentences — no bullets, no recited list.
5. Ask a plain one-off search question (not company research) — confirm the Sources list still works correctly for a single search call.

## Business Reports

JARVIS can compile a structured business report — a visual card with real sections and sources — after researching a company, market, or investment idea. No new setup needed; this reuses web search, market data, and page reading already configured.

1. Ask "Give me a business report on `<a real, findable company>`." Expected: JARVIS researches it (visible in the tool-call metadata), speaks a brief summary, and a structured report card appears with real, non-generic section content.
2. Confirm the report card shows real headings/sections (fine for a card, not spoken text) while the chat reply text itself stays voice-safe — no bullets or headers in what's actually spoken/displayed as the message body.
3. Ask for a report on a public company. Expected: a section reflects a real current price from market data, not an invented number.
4. Ask for a report on something where a section genuinely has nothing to report (e.g. financials for a private company). Expected: that section is omitted, not filled with fabricated content.
5. Confirm the report card's sources are real, clickable links.
6. Quickly re-verify market data and company research still work unaffected.

## Content Creation

JARVIS can draft social media captions, YouTube/podcast scripts, and marketing copy — always researched first and grounded in what it actually found, shown as a copyable card. No new setup needed; this reuses web search and news already configured.

1. Ask "Write an Instagram caption about `<a real, current topic>`." Expected: JARVIS researches it first (visible in tool-call metadata), speaks a one-line summary, and a content card appears with a real, Instagram-styled caption (punchy hook, 3-5 hashtags) grounded in something findable — not generic filler.
2. Ask for a LinkedIn caption and an X post on the same topic. Expected: each reflects that platform's distinct style — LinkedIn professional/insight-driven with 1-2 hashtags, X concise with at most 1-2 hashtags.
3. Ask "Write a YouTube script about `<a real topic>`." Expected: a hook, body segments, and a call-to-action, written to be read aloud.
4. Ask for marketing copy for a product or service. Expected: short and benefit-focused with a clear call-to-action.
5. Confirm the content card's copy button actually copies the text, and that JARVIS's spoken/text reply itself stays voice-safe — no hashtags or bullets in what's actually spoken, only in the card.
6. Ask about a topic where little real information exists. Expected: JARVIS says so or keeps the content honest rather than inventing specific claims.
7. Quickly re-verify business reports and company research still work unaffected.

## Subtitle Generation

JARVIS can generate a real `.srt` subtitle file for a video/audio file, saved next to the source file, with optional translation — the first feature that processes an actual media file rather than just chatting. Two ways to give it a file: type a local path, or upload one directly in the chat.

1. First-time setup: install `ffmpeg` if it isn't already (e.g. `winget install ffmpeg`, or from ffmpeg.org). Verify with `ffmpeg -version` in a terminal.
2. **Upload flow:** ask "I want to add subtitles to my video" with no file path given. Expected: JARVIS responds with an upload prompt card, not a plain text question.
3. Click "Choose File" (or drag a file onto the card) and pick a real video file, ideally a few hundred MB to actually see progress. Expected: a progress bar advances during upload; once complete, JARVIS automatically generates subtitles for the uploaded file with no further typing — a `.srt` appears next to the uploaded copy in `backend\data\uploads\`, and a preview card with a working copy button appears in the chat.
4. **Path flow:** ask JARVIS to generate subtitles for a real local video/audio file by path (e.g. "generate subtitles for `C:\path\to\clip.mp4`"). Expected: works the same as the upload flow — a `.srt` file appears next to the source file, and a preview card appears in chat. Confirms both input modes coexist.
5. Ask for the same file again (either flow). Expected: it doesn't overwrite the first `.srt` — a distinctly-named file appears instead (e.g. `clip-2.srt`).
6. Ask for subtitles with a target language (e.g. "...and translate them to Spanish"). Expected: the subtitle text is genuinely translated while timing stays intact.
7. Ask for subtitles for a nonexistent file path. Expected: a clear "couldn't find that file" message, not a crash.
8. Try a path (or upload) to a non-media file (e.g. a `.txt` file). Expected: a clear extraction error, not garbled output or a hang.
9. Quickly re-verify voice input (mic button) still works — it uses the same Groq transcription API, just a different endpoint call.

## Silence Removal / Rough Cuts

JARVIS can detect and remove silent gaps from a video/audio file, saving a new `-edited` copy — reuses the same upload/path flow as subtitle generation above.

1. Upload or point to a real video/audio file with clear pauses (e.g. a podcast clip) and ask JARVIS to remove the silence. Expected: a new `-edited` file is produced, is shorter than the original, and the pauses are genuinely gone when played back.
2. Confirm the result card shows accurate original/new duration and seconds-removed stats matching what was actually produced.
3. Ask again with a custom threshold (e.g. "only remove silences longer than 2 seconds"). Expected: fewer/different cuts than the default pass.
4. Try a file with no meaningful silence (or a very short clip). Expected: a clear "nothing to remove" message, not a needless duplicate file.
5. Run it twice on the same file. Expected: the second run produces a distinctly-named file (e.g. `clip-edited-2.mp4`), not an overwrite.
6. Ask "remove the silence from my podcast" with no file given. Expected: the upload prompt card appears (same as subtitle generation), and after uploading, silence removal is what runs — not subtitle generation.
7. Quickly re-verify subtitle generation and the upload flow still work unaffected.

## Highlight Detection

JARVIS can transcribe a video/audio file, identify the most compelling moments, and cut each into its own clip — reuses the same upload/path flow as subtitle generation and silence removal above.

1. Upload or point to a real video/audio file with clearly distinct moments (e.g. a podcast with a few notable quotes or jokes) and ask JARVIS to find highlights. Expected: multiple clips are produced, each corresponding to a genuinely distinct, sensible moment — not arbitrary/repeated slices.
2. Confirm the result card lists each clip's time range, reason, and file path accurately. Play back a generated clip and confirm it actually contains the highlighted moment, correctly timed.
3. Ask again with a custom count (e.g. "just find the best 2 highlights"). Expected: the count is respected.
4. Try a very short or low-content file where genuine highlights are hard to identify. Expected: a clear "couldn't identify any highlights" message, not fabricated/nonsensical clips.
5. Run it twice on the same file. Expected: the second run's clips don't overwrite the first (independently non-clobbering per clip).
6. Ask "find highlights in my podcast" with no file given. Expected: the upload prompt card appears, and highlight detection is what runs after uploading — not subtitle generation or silence removal.
7. Quickly re-verify subtitle generation and silence removal still work unaffected.

## TV Control

The first Studio Automation feature — JARVIS controls three TVs (TCL/Roku, Samsung, LG) directly, no Home Assistant involved. Each TV needs its IP (and MAC address, for Wake-on-LAN power-on) configured in `backend\.env` before this works.

1. Before configuring any TV, ask JARVIS to turn on a TV. Expected: a clear "not configured yet" message, not a crash — this works immediately, no client details needed.
2. Once IPs/MACs are configured (and each TV's `Fast TV Start`/`Quick Start`/equivalent standby-wake setting is enabled), restart the backend. Ask JARVIS to turn each TV off, then back on by name. Expected: real responses, including power-on from fully off via Wake-on-LAN for all three.
3. For the Samsung and LG TVs, confirm a one-time pairing prompt appears on the TV screen the first time, and that later commands don't re-prompt.
4. Ask for volume up/down and mute on each TV. Expected: real, audible/visible changes.
5. Ask to launch an app by name on the Samsung or LG TV (e.g. "open Netflix on the LG"). Expected: the app actually opens. For the TCL/Roku, expect it to ask for or need a numeric app ID rather than a name.
6. Ask JARVIS to control "the TV" without naming one, when more than one has been discussed recently. Expected: it asks which TV rather than guessing.
7. Confirm every reply stays voice-safe — a plain spoken confirmation, no tool syntax leaking through.

## "What Am I Forgetting?" Mode

The first of the client's "10 Core Functions" — reviews open tasks, upcoming calendar events, and saved memories to flag what's genuinely worth surfacing. Uses only existing data (no new integrations).

1. With a mix of overdue tasks, upcoming tasks, tasks with no due date, at least one near-term calendar event, and a few saved memories in place, ask "what am I forgetting?" Expected: JARVIS calls `review_forgotten_items`, then produces a "What You Might Be Forgetting" report card with genuinely relevant flagged items — not a dump of every task/memory verbatim.
2. Clear out tasks/events/memories (or use a fresh state) and ask again. Expected: JARVIS says something like "nothing stands out" rather than fabricating a report.
3. Ask the same question while Google Calendar isn't connected. Expected: no error — calendar data is simply absent/noted as unavailable, tasks and memories are still reviewed.
4. Confirm the spoken reply stays voice-safe (brief summary, no bullets), with detail living in the report card.
5. Quickly re-verify plain task listing, calendar listing, and business reports still work unaffected.

## Opportunity Engine

The second of the client's "10 Core Functions" — on-demand, topic-driven opportunity research. Reuses existing search tools and `create_business_report`; no new tool, no new UI.

1. Ask "find opportunities in [some market/topic]." Expected: JARVIS researches across at least two of web_search/get_news/search_patents/search_papers and produces an "Opportunities in X" report card with specific, sourced opportunities — not generic advice.
2. Ask about an obscure/narrow topic with little real information available. Expected: JARVIS says it didn't find anything concrete rather than fabricating opportunities.
3. Quickly re-verify plain web_search, get_news, and business reports still work unaffected.

## Error Detector / Decision Simulator

The fourth and fifth of the client's "10 Core Functions" — on-demand only (JARVIS doesn't critique unprompted). Reuses `create_business_report`; no new tool, no new UI.

1. Describe a plan with an obvious flaw and ask JARVIS to stress-test it. Expected: it names the actual weakness (not generic boilerplate) via a "Stress Test: X" report card.
2. Ask JARVIS to simulate a decision (e.g. "simulate the outcome of switching vendors for X"). Expected: distinct best-case/likely/worst-case sections and the key variables that could change the outcome.
3. Describe a genuinely solid plan with no real flaws and ask for a stress test. Expected: JARVIS says it holds up rather than manufacturing fake problems.
4. Mention a plan in passing without asking for a stress test or simulation. Expected: JARVIS does NOT unprompted critique it.
5. Quickly re-verify Opportunity Engine and "What Am I Forgetting?" still work unaffected.

## Second Brain (lightweight v1)

Organizes saved memories into categories (person/project/document/decision/goal) instead of one flat list. Reuses the existing memory store; no new table, no new UI.

1. Tell JARVIS three distinct facts in separate messages: something about a person ("Sarah is the lead on Project X"), a decision ("we chose direct TV integration over Home Assistant for full source ownership"), and a goal ("Project X launches in October"). Expected: each saves normally, no category spoken aloud (it's an internal tag).
2. Ask "what do I know about Project X?" Expected: a synthesized answer pulling the relevant entries, not a flat recitation of every saved memory.
3. Ask "why did we decide to skip Home Assistant?" Expected: JARVIS recalls the decision and explains the reasoning.
4. Save something generic with no clear category (e.g. "I prefer dark mode"). Expected: it still saves and is still recallable normally.
5. Quickly re-verify plain save_memory/get_memory (no category involved) still works exactly as before.

## Learning System (lightweight v1)

Tracks whether you accept or dismiss JARVIS's recommendations (Opportunities/Stress-Test/Decision-Simulation/Forgotten-Items) and factors recent patterns into future ones. Feedback is inferred from conversation, not an explicit button — no frontend change.

1. Ask for an opportunity search, then respond dismissively ("not relevant to me"). Confirm no visible error/UI change (the log call is silent).
2. Ask about a similar/related opportunity topic again later in the same session. Confirm JARVIS asks before re-surfacing rather than repeating the dismissed angle blind.
3. Ask for a stress-test and respond positively ("great catch, let's fix that"). Confirm it doesn't break the normal reply.
4. Confirm the feedback-pattern context never leaks into JARVIS's spoken replies as raw data (no "you dismissed X twice" recitation) — only natural, occasional influence.
5. Quickly re-verify Opportunity Engine, Error Detector/Decision Simulator, "What Am I Forgetting?", and Second Brain still work unaffected.

## Adding a new feature?
When a new increment's plan is executed, append its manual test steps here as a new section, in the same format.
