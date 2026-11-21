# Usability heuristics, as checks

Nielsen's ten heuristics, each turned into questions you can answer yes or no
while using the screen. A "no" is a candidate finding. Keep it only if you can
name who it hurts.

## 1. Visibility of system status
- Does every action show that it happened, within about 1s, or show progress if it takes longer?
- Is there a loading state that keeps the layout from jumping when the data arrives?
- After saving, is it clear what was saved and where it went?

## 2. Match with the real world
- Are things named the way users name them ("notifications", not "webhook config")?
- Are dates, numbers and currency in the user's format?
- Do icons mean what they usually mean? Is an unusual one labelled?

## 3. User control and freedom
- Can every destructive action be undone, or does it ask first and name exactly what will be lost?
- Do Escape and Cancel get out of every dialog, wizard and edit mode without losing earlier work?
- Does the back button do what the user expects?

## 4. Consistency and standards
- Does the same action use the same word, component and position everywhere?
- Do links look like links and buttons like buttons, and is there one primary button per view?
- Does it use the project's tokens and shared components rather than one-off values and lookalikes?

## 5. Error prevention
- Are impossible inputs prevented: date pickers, input masks, disabled buttons with a reason shown?
- Are risky defaults avoided, such as "delete all" preselected?
- Is form input validated before submission, without scolding mid-typing?

## 6. Recognition rather than recall
- Are options visible rather than something the user has to remember?
- Does each form keep context: what this is for, and which step of how many?
- Are recent and frequent items easy to get back to?

## 7. Flexibility and efficiency
- Are the frequent actions one step away? Do lists have search, sort or filter once they grow?
- Do keyboard shortcuts exist for power users without getting in the way of others?

## 8. Aesthetic and minimalist design
- Does each screen lead with its main task? Is secondary information demoted, not removed?
- Is there one clear visual hierarchy: a heading, a primary action, then supporting content?

## 9. Help users recognize, diagnose and recover from errors
- Does each error say what happened, why, and what to do next, in plain words, next to the field?
- Is the user's input kept after an error?

## 10. Help and documentation
- Is help available at the point of need (an empty state that explains, an inline hint) rather than only in docs?

## States to force on every screen

| State | What to check |
| --- | --- |
| Loading | Skeleton or spinner, no layout jump, and a timeout message if it takes long |
| Empty | Says what will appear and how to add the first one |
| Partial | One item, many items, and a very long item (names, titles, numbers) |
| Error | Network down, server 500, validation failure, each with a way forward |
| Success | Confirmation, and where the result now is |
| No permission | Explains why, and who can grant it |
| Offline / slow | What still works, and what the user is told |
