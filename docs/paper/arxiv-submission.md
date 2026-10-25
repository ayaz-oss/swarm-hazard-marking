# arXiv submission: metadata and steps

Everything to paste into the arXiv form. The PDF to upload is `docs/paper/draft.pdf`.

## Metadata

**Title**

Lost Teammates as Hazard Sensors: Stigmergic Marking of Robot Failures in a Foraging Swarm

**Authors**

Ayaz Nasyrov

**Abstract** (plain text, under arXiv's 1,920-character limit)

Robots exploring unknown environments are often lost to hazards their sensors cannot detect, and swarm robotics usually treats such losses as damage to tolerate. We ask whether a decentralised foraging swarm with only local sensing can instead use the failures of its teammates as information about where a hazard is. In our controller, a robot that finds a teammate's wreck deposits a decaying repellent mark, analogous to the "no entry" pheromone of Pharaoh ants, and robots steer away from strong marks. We compare it with controllers that ignore wrecks, avoid only wrecks in view, add a risk trade-off, keep per-robot maps or shared sighting records, broadcast risk-limit alerts, or know the hazard, in a simulated 20-robot central-place foraging task. Hypotheses and analyses were pre-registered and runs are paired by seed (38,600 runs). With site fidelity, marking lost fewer robots than avoiding visible wrecks (A12 = 0.66, Holm p = 1e-7) and delivered slightly more items than ignoring the hazard (A12 = 0.56, Holm p = 9e-4); in a control where robots fail at random places, its item cost stayed within a pre-registered bound. The robot savings held across swarm sizes, hazard placements and sizes, strong detection noise, a moving hazard and two simultaneous hazards, and under a second foraging model. Per-robot maps exchanged between neighbours showed no detectable difference from a shared field, and literature-inspired alert broadcasts lost more robots than plain avoidance. In a pre-registered replication in the Webots physics simulator, with real robot bodies and collisions, marking again lost fewer robots (A12 = 0.61, Holm p = 8e-6), but the small item gain was not detectable. Code, data and pre-registration are openly available.

**Comments**

21 pages, 10 figures. Pre-registered study. Code, data and pre-registration: https://github.com/ayaz-oss/swarm-hazard-marking, archived at https://doi.org/10.5281/zenodo.23637280

**Primary category:** cs.RO (Robotics)
**Cross-list:** cs.MA (Multiagent Systems)
**Licence:** CC BY 4.0
**MSC / ACM class:** leave empty

## Steps

1. **Register** at https://arxiv.org/user/register using your **UCL email address**. Fill in your
   name exactly as on the paper (Ayaz Nasyrov) and your affiliation (University College London).
   Confirm the email arXiv sends you.
2. **Start a submission**: log in → "Start New Submission".
3. **Licence**: choose "Creative Commons Attribution 4.0" (CC BY 4.0).
4. **Archive and category**: Computer Science → **Robotics (cs.RO)**.
5. **Endorsement**: if arXiv says you need an endorsement for cs.RO, it shows a message with an
   **endorsement code** (six characters) and sends you an email with a link. Keep that page/email:
   this code goes into the email to Dr Kanoulas. You can save the submission and come back later.
6. **Upload**: add `draft.pdf`. arXiv accepts a PDF that was not made with LaTeX; ours was made
   from HTML, so this is allowed. If the checker complains, tell me and I will convert the paper
   to LaTeX.
7. **Metadata**: paste the title, author, abstract and comments above. Add the cross-list cs.MA.
8. **Preview** the processed PDF, check the first page and figures, then **submit**. If the
   endorsement is still pending, the submission waits until Dr Kanoulas endorses you.
9. arXiv announces new papers on weekday evenings (US Eastern time). You will get an
   arXiv identifier like 2610.xxxxx.

## Before submitting, check

- The first page shows your name and "Foundation Year, University College London".
- The first page says "Preprint", not "Working draft" (already changed).
