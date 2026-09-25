# The reply for each stage

Shapes, not scripts. Every example below is there to show the moves; a reply
that reads like one of them word for word has not been written for its thread.
Placeholders like «this» mark what must come from the thread or the profile —
`draft_check.py` blocks a draft that still contains a bracketed placeholder.

## First contact, good fit (intent: engage)

The goal is a call. Say yes to the conversation, ask the one or two things that
would stop it being worth the call, and offer times.

```
Hi «first name»,

Thanks for reaching out. «The specific thing: the team, the product, the
problem they named» is close to what I work on.

Before we talk: what is the salary range, and how many office days does the
role have? If that fits, I could do «slot one» or «slot two» («timezone»).

Best,
«name»
```

## First contact, too little said (intent: qualify)

Interest is conditional; the reply earns the facts first. Keep it short so the
recruiter answers from their phone.

```
Hi «first name», thanks for thinking of me.

Could you tell me a bit more first: which company is it, what is the range,
and is it permanent or contract? Happy to set up a call if it lines up.

«name»
```

## Agency, client not named

The name comes before the CV, every time.

```
Hi «first name», thanks, this could be interesting.

Which company is the role with? I keep track of where my profile goes, so I
only agree to submissions once I know the client. And what range have they
budgeted?
```

## Freelance project broker

They filter on availability and rate first; answer those in the first line if
the profile allows it, otherwise ask for their budget.

```
Hallo «first name»,

danke für die Anfrage. Ich bin ab «earliest_start» verfügbar. Können Sie mir
Endkunde bzw. Branche, Laufzeit, Remote-Anteil und das Budget für den
Tagessatz nennen?

Viele Grüße
«name»
```

(The day rate is stated only when `day_rate.say` is set.)

## They answered, still a fit (interested → scheduling)

Stop asking; schedule. Offer concrete slots from `availability` and ask who
will be on the call.

```
Thanks, that all fits. «slot one» or «slot two» would work for me, or send
me a link with your slots. Will it be with you or with the hiring manager?
```

## Scheduling details

Confirm exactly what was agreed — day, date, time, timezone, medium — so a
wrong assumption surfaces now rather than at the call.

```
Great: «weekday», «date» at «time» «timezone», on «medium». Looking forward
to it.
```

Record the thread as `scheduled` and hand it to the job-hunter pipeline and
interview-prep (the `reply-ledger` skill has the commands).

## Decline (intent: decline)

Two sentences. The door stays open because recruiters move companies.

```
Hi «first name», thanks for thinking of me. «One honest reason: it's on-site
in Munich / it's a contract role and I'm only looking at permanent», so I'll
pass, but I'd be glad to hear about «what does fit» in future.
```

## Follow-up after silence

Add something, do not just bump. Two follow-ups, then close the thread.

```
Hi «first name», following up on «the role» from «date». Still interested.
Is the process moving, or has it been filled?
```

## An offer, or anything that sounds like one

Not the actor's to answer. Acknowledge, and hand it to the user:

```
Thank you, that's great to hear. I'll review the details and come back to
you by «date the user chooses».
```

The date is the user's. The acceptance, the counter and the negotiation are
the user's, in their own words.

## German register

- Formal by default with a stranger: *Sie*, "Sehr geehrte Frau «surname»" only
  if they wrote that way; "Hallo «first name»" matches most LinkedIn messages.
- Mirror *du* if they used it.
- "Viele Grüße" closes most messages; "Beste Grüße" is fine; "Mit freundlichen
  Grüßen" is for formal email.
