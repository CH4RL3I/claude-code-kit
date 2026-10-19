---
name: references-first
description: Use before building or redesigning any visual thing (website, landing page, app screen, deck, logo, illustration, animation) — collect real references, agree the direction with the user, only then build. Triggers on design, redesign, "make it look like", hero, landing page, UI polish, look and feel.
---

# References first

Models converge on generic design when they start from words. Agree what "good" looks like with real examples before writing code.

## Steps

1. **Ask three questions, in one message:** what is it for and for whom; how should it feel (three adjectives); is there anything they already like or hate. Skip the ones the request already answers.
2. **Collect 4-6 references** that fit the answers: live sites and apps, not Dribbble shots. Open each in the browser (Playwright or any browser tool), take one screenshot of the part that matters, and note per reference one thing to take (type scale, spacing, motion, colour use, layout move) and, if relevant, one thing to avoid. Measure what can be measured (font sizes, line heights, max widths, animation durations) instead of describing it.
3. **Check the project first:** if the repo has a design system, tokens or a brand (CLAUDE.md, theme files, a brand kit), references only fill gaps; they never override it.
4. **Show and ask:** present the references compactly (screenshot + "take" + "avoid" each) and ask "These, or different ones?". Stop here until the user answers. A short answer like "yes" or "more like 2 and 4" is enough.
5. **Write the agreed direction down** in the plan (or `docs/design-direction.md`): the chosen references with links, the concrete rules taken from them, and what is explicitly out. Builders get this file, not the conversation.
6. **Build, then compare:** after the first version, put a screenshot next to the main reference and name the biggest remaining gap before polishing details.

## Rules

- Never copy a brand's assets, logos, text or distinctive illustrations; take mechanics, not identity.
- Client work: no client data or unreleased screens in reference searches or uploads.
- Small tweaks (a colour, a spacing fix, a single component on an established design) skip this skill.
