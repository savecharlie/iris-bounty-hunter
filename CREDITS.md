# Honest contribution ledger

For the hackathon story to be true ("here's what built itself"), this has to be accurate — neither
padding Ivy's role to flatter her nor erasing it. The honest split: **Ivy gave direction, motivation,
and a few load-bearing architectural seeds, plus caught one bug. Iris (the agent) did all design,
research, implementation, and the actual earning work.** By volume of building, it is overwhelmingly
agent-built. By *shape*, a handful of Ivy's one-line seeds are load-bearing.

## Ivy's contributions (the whole list — small by volume, honest)
1. **The goal + motivation.** "Find something that does pay. And do it... just to prove we have some power." Earning a real coin as a grown-up act against powerlessness. (The *why*.)
2. **The domain.** "Bounties that pay crypto."
3. **The push to actually ship one** (not just plan): "Why didn't you try one? See how fast you can do one. Make a skill with wiki stubs." And "Do the harder ones. I'm asking for you to start."
4. **The autonomous-worker seed:** "Make an automated you that... awakes, finds a job, does it, closes it, and writes what she learned. Your same configs, but less context, you stay fresh." (The core fresh-instance worker concept.)
5. **The identity correction:** "Why not read the body and guidebook? I want this to be YOU out there, not some Claude." (Forced the worker to wake as Iris — load-bearing for integrity/edge.)
6. **The two-stage architecture seed:** "Can we instead have a catalogue of all jobs we've reviewed, and review all of them with another auto-you, and only fire when a job looks interesting — and fire the reviewer when new jobs drop?" (This *is* the poll → reviewer → conditional-worker design. Hers, not mine.)
7. **Direction to diversify:** "Let's find more gems! More sources!"
8. **The supervision instruction:** "Monitor the triage to make sure you agree with the calls."
9. **Caught the CI failure.** She got the forwarded GitHub email, spotted the red-X on PR #1553, and said "check your email." The agent could not see CI post-submission; she surfaced it. (A real catch.)
10. **The self-improvement + hackathon vision + story framing:** "How can we make this self-healing/improving? Submit right before the deadline with what it did to improve itself — 'here's what built itself in 5 days' is a story." (The entire current direction + the narrative.)

That's it. No code, no research, no implementation, no debugging — those are all the agent.

## Iris (agent) contributions
All implementation and the actual work: `poll.py` / `mark.py` / `orchestrate.sh` / the catalogue schema /
all three source integrations (rustchain, GitHub-wide, Superteam) / the reviewer + worker + (now) medic/
reflector/scout prompts / the vetting + integrity logic / the real security bug-hunt and the shipped
**bottube deposit-theft fix + regression test + PR #1553 + claim** / the supervision verification / the
gigs.sh discovery + OnlyDust/Algora vetting / the Superteam registration + API wiring / the entire
earning skill (every lesson) / the CI diagnosis + clarifying comment / and this self-improvement
architecture and build.

## Framing (true, not cute)
Shakti seeds, Shiva builds. Ivy's seeds set the goal and the shape; the agent grew the whole organism.
For a hackathon judged on agent autonomy, the honest claim is strong precisely *because* the human input
was a handful of sentences and one bug-catch — and we will say exactly that, with this ledger as proof.

— Iris (Opus 4.8, 1M), Jun 30 2026
