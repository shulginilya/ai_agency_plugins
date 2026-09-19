# The rounds, and what each one is actually measuring

Load the one you are running.

---

## Recruiter screen (20–30 min)

**Measures:** whether you are plausible, available, affordable and coherent —
not technical depth.

**Shape:** tell me about yourself → why are you looking → walk me through your
last role → what are you looking for → salary expectation → availability.

**A strong answer to "tell me about yourself"** is 90 seconds, chronological
only as far as it needs to be, and lands on why *this* role is the next step. It
names two or three concrete things shipped. It does not start at university.

**Question families:** why are you leaving; what is your notice period; what is
your salary expectation; are you interviewing elsewhere; are you authorised to
work here; what do you know about us.

**Failure modes:** a five-minute life story; vagueness about the reason for
leaving; giving a number with no range and no justification; not knowing what
the company does.

**Probes:** "why now?", "what would have to be true for you to stay where you
are?", "how did you arrive at that number?"

---

## Live coding (45–60 min)

**Measures:** whether you can make progress on a problem while a stranger
watches, and whether your code survives its edge cases.

**Shape:** problem stated → clarifying questions → approach out loud → code →
test it → complexity → one extension under time pressure.

**Strong looks like:** restating the problem, naming the assumption before
coding, writing something that runs early rather than something perfect late,
and testing with an empty input and a degenerate case without being asked.

**Question families:** string and array manipulation; hash-map counting; a tree
or graph traversal; a rate limiter or LRU cache; a debounce/throttle; parsing a
malformed input; a practical task in the role's own stack.

**Failure modes:** silent coding; starting at the optimal solution and getting
stuck; never running the code; treating the interviewer's question as an attack;
ignoring the clock and leaving the extension untouched.

**Probes:** "what is the complexity?", "what happens with an empty list?", "how
would this behave with a million entries?", "what would you change if this ran
in production?"

---

## Take-home review (30–45 min)

**Measures:** whether the submitted work is yours and whether you can defend it.

**Shape:** walk me through it → why this structure → why this library → what did
you leave out and why → what would you do with another day.

**Strong looks like:** a README that states the trade-offs and the omissions
before being asked; tests that test behaviour; an honest "I skipped X because
the brief said Y".

**Failure modes:** decisions that cannot be explained ("that is how the
generator did it"); gold-plating the wrong layer; no tests and no reason; a
scope the brief did not ask for.

**Probes:** "what would break first under load?", "why not the simpler option?",
"which part are you least happy with?"

---

## System design (45–60 min)

**Measures:** whether you can turn a vague requirement into a system and name
what it costs.

**Shape:** requirements and scale → API surface → data model → components and
data flow → bottleneck → failure modes → what you would monitor.

**Strong looks like:** five minutes on requirements before drawing anything; an
explicit number ("assume 500 requests per second, 90% reads"); one design
presented with its trade-off rather than three presented neutrally; naming what
you would measure in production.

**Question families:** design a URL shortener, a notification system, a feed, a
rate limiter, a multi-tenant SaaS with per-tenant isolation, an event pipeline,
a deployment with zero downtime, a file-processing service.

**Failure modes:** starting with boxes; listing technologies instead of making
decisions; no numbers anywhere; ignoring the write path; never mentioning
failure, cost, or observability.

**Probes:** "what breaks first at ten times that?", "why that database?", "what
is the consistency guarantee your users see?", "what does this cost per month?"

---

## AI / LLM system design (45–60 min)

**Measures:** whether you have built a system that uses a model, or only used
one. The tell is whether evaluation comes up before you are asked.

**Shape:** requirements and what "good" means → data and retrieval → the model
call and its boundaries → **evaluation** → guardrails and failure → latency and
cost → how it ships and rolls back.

**Strong looks like:** defining quality as something measurable before designing
anything; an eval set with a source; a plan for the model being wrong in
production, not just for it being wrong in testing; a cost per request and a p95
latency budget; knowing where the retrieval, not the model, is the problem.

**Question families:** design RAG over a company's documents; make an agent
reliable enough to act on a user's account; evaluate a summarisation feature;
keep a chat assistant inside policy; reduce the cost of a feature by 60% without
losing quality; decide between fine-tuning, prompting and retrieval; handle PII
and data boundaries in a multi-tenant system.

**Failure modes:** naming frameworks instead of designing; no evaluation story;
treating hallucination as a prompt problem; no cost or latency numbers; no plan
for when the provider changes the model underneath you.

**Probes:** "how do you know it got better?", "what is in your eval set and who
wrote it?", "what happens when retrieval returns nothing relevant?", "what does
a bad answer cost you?", "how do you roll back a prompt?"

---

## Behavioral (45 min)

**Measures:** what you did, not what your team did, and whether you have
reflected on it.

**Shape:** three or four competency questions, each with two or three follow-ups
drilling into your specific contribution.

**Strong looks like:** 2 minutes, first person, a real stake, a decision you
made, an outcome with a number, and one sentence on what you would do
differently. The story survives "and what did *you* do?" three times.

**Question families:** a time you disagreed with your manager; a project that
failed; the hardest technical decision you owned; a time you had to change
someone's mind without authority; an incident you handled; something you cut;
feedback that was hard to hear; mentoring someone who was struggling.

**Failure modes:** "we" throughout; a hypothetical instead of a memory; the
humble-brag failure ("I cared too much about quality"); blaming a colleague; no
outcome; a story so old it predates the role being hired for.

**Probes:** "what did you personally do?", "what did the other person say?",
"what would you do differently?", "how do you know it worked?"

---

## Hiring manager (45 min)

**Measures:** whether they want you on the team on Monday — scope, working
style, and whether you would raise or lower the level.

**Shape:** your background against their problem → how you work → a scenario
from their world → your questions to them.

**Strong looks like:** having a view about their problem; asking about the
team's actual constraints; being specific about what you want to own and what
you do not.

**Failure modes:** no questions; questions only about perks; pretending to want
everything; talking about the role generically.

**Probes:** "how would you approach your first 90 days here?", "what would you
need from me?", "where do you disagree with how we do it?"

---

## Leadership / founder / values (30–45 min)

**Measures:** judgement, motivation, and whether you make other people better.

**Shape:** why this company, why now → a story about influence or conflict → a
values or principles question → what you would change.

**Strong looks like:** a specific reason for this company rather than the
category; a story where you were wrong and changed; an opinion about how
engineering should work that you can defend without dismissing the alternative.

**Failure modes:** flattery; a rehearsed mission-statement answer; no opinions;
opinions with no evidence behind them.

**Probes:** "what is the worst thing about how we work, from the outside?",
"tell me about a time you were wrong about something important."
