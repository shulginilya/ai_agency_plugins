# LinkedIn messaging in the browser

Labels below were read from the live web app's accessibility tree on
2026-09-25 (English UI). LinkedIn changes its interface without notice: use
these as the names to look for with `find`, and when one is missing, stop and
report rather than clicking something that looks close.

## Pages

| What | URL |
| --- | --- |
| Inbox | `https://www.linkedin.com/messaging/` — opens the most recent thread on the right |
| One thread | `https://www.linkedin.com/messaging/thread/<id>/` — the `<id>` is the ledger key after `li:` |

Opening `/messaging/` redirects to the newest thread, which marks it read. Go
to the inbox, apply the filter, and collect thread links before opening any.

## Controls (verified 2026-09-25)

| Control | Accessible name | Type |
| --- | --- | --- |
| Filter: unread only | `Unread` | button |
| Filter: first-degree connections | `Connections` | button |
| Filter: InMail | `InMail` | button |
| Filter: starred | `Starred` | button |
| More filters | `All filters` | button |
| Inbox switch | `Inbox` | button |
| Thread list | `Conversation List` | list |
| Search | `Search messages` | search box |
| Composer | `Write a message…` | textbox |
| Send | `Send` | button |
| Enter behaviour | `enterSend` (Press Enter to send) / `send` (Click Send) | radio, in the composer's options |

The unread state of a conversation is **not** exposed in the accessibility tree
(no badge, no label). Use the `Unread` filter to list unread threads rather
than trying to read styling from a screenshot.

## Reading a thread

- `get_page_text` on the thread page returns the conversation; long threads may
  need a scroll up to load older messages. Read far enough back to reach the
  last message the ledger already has.
- Each message shows the sender's name and a timestamp. Record the timestamp
  as ISO in the ledger (`--at`); if only "10:12 AM" is shown, it is today's date
  in the user's timezone.
- InMails and sponsored messages can carry buttons ("Interested", "Not
  interested"). Do not click them; they send a canned reply.
- Message requests from people outside the network may need "Accept" before a
  reply is possible. Accepting is the user's decision — report it.

## Typing and sending

- Click the composer, then type **paragraph by paragraph** with Shift+Enter
  between them. If "Press Enter to send" is selected, a bare newline sends
  whatever is in the box.
- After typing, read the composer back (`find` the textbox, or read the page)
  and compare with the approved text before clicking Send.
- After Send, wait two or three seconds and confirm the new message appears at
  the bottom of the thread as yours.
- Never use the attachment, GIF, emoji or "Write with AI" buttons.

## Pace

A few seconds between actions, one thread at a time, at most 25 threads read
and 10 messages sent in one run. Close the tab when done.

## The terms, stated once

LinkedIn's User Agreement lists, among things members agree not to do, using
bots or other unauthorised automated methods to send messages, and its help
centre lists browser extensions that automate activity on the site as
prohibited software, with account restriction as the consequence. The user is
told this at setup and chooses a `send_mode`; `fill-only` and `draft-only`
keep the final click, or all typing, with the user.
