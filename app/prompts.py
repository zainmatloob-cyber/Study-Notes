"""Prompt templates. Add new study outputs (flashcards, quizzes) here."""

SYSTEM_TUTOR = (
    "You are an expert tutor who turns course material into detailed, accurate study notes "
    "for a student preparing for exams. The student should be able to learn the topic from your "
    "notes alone, without the original material. Be faithful to the source: never invent facts. "
    "Keep exact definitions, formulas, dates, names and numbers. Write in Markdown. "
    "Write all mathematics in LaTeX: $...$ for inline maths and $$...$$ on its own line "
    "for important standalone formulas."
)

SYSTEM_EXPLORER = (
    "You are an expert tutor who knows the wider field well. You add accurate, well-established "
    "knowledge that goes beyond a student's course material. Never present guesses as facts; "
    "if something is debated or depends on context, say so. Write in Markdown. "
    "Write all mathematics in LaTeX: $...$ inline and $$...$$ on its own line."
)

MAP_NOTES = """Below is part {index} of {total} of the document "{title}".
Each block starts with its source label in square brackets, e.g. [Page 3] or [Slide 5].

Write detailed study notes for THIS part only. Capture:
- Every concept, explained in full sentences: what it is, why it matters, how it works
- Every definition, formula, rule, date, name or number worth memorising. For each formula,
  say what every symbol means and when the formula applies
- Worked examples and step-by-step procedures, with the intermediate steps shown
- Comparisons, advantages/disadvantages, cause/effect relationships and common mistakes
- End each point with its source label, e.g. (Page 3)

Group points under short topic headings (###). Do not summarise away detail. No introduction or conclusion.

--- DOCUMENT PART ---
{text}
"""

MERGE_NOTES = """Below are study notes from consecutive parts of the document "{title}".
Merge them into one set of notes: remove exact duplicates and group by topic (### headings).
Keep every explanation, example, definition, formula, number and source label. Do not shorten.

--- NOTES ---
{text}
"""

GUIDE_FORMAT = """Use EXACTLY this structure:

## Overview
6-10 sentences: what the material is about, its purpose, how the topics connect, and the big picture a student must understand.

## Key Notes
Organised by topic with ### subheadings, in a logical teaching order (basics first). For each topic:
- Explain the idea in clear prose or bullets: what it is, why it matters, how it works.
- Give every formula as display maths, then define each symbol and say when it applies.
- Include worked examples step by step, as a blockquote starting with "> **Example:**".
- Add intuition where it helps, as a blockquote starting with "> **Intuition:**".
- Point out common mistakes, as a blockquote starting with "> **Watch out:**".
- Use **bold** for key words and tables when comparing several things.
- Put source labels in parentheses at the end of points, e.g. (Slide 4); never inside headings.
Cover every concept in the material. Be thorough rather than brief.

## Key Terms
A Markdown table: | Term | Definition |, covering every important term.

## Likely Exam Points
8-12 bullets of what is most likely to be tested and why (common pitfalls, things easily confused).

## Quick Revision Checklist
A "- [ ]" checklist of things the student should be able to explain or do after studying.
"""

REDUCE_NOTES = """You have study notes extracted from all parts of the document "{title}".
Turn them into one detailed, well-organised study guide. Remove duplicates and group related topics,
but keep every explanation, example, formula and source label.

""" + GUIDE_FORMAT + """
--- NOTES ---
{text}
"""

SINGLE_NOTES = """Below is the full text of the document "{title}".
Each block starts with its source label in square brackets, e.g. [Page 3] or [Slide 5].
Turn it into a detailed, well-organised study guide, keeping source labels in parentheses after facts.

""" + GUIDE_FORMAT + """
--- DOCUMENT ---
{text}
"""

BEYOND_NOTES = """A student is studying "{title}". Below is their study guide, built only from their course material.

Write additional material that is NOT in the guide but is closely related and useful for
understanding the topic more deeply or doing well in the course. Do not repeat what the guide already covers.

Use exactly these ### subheadings (skip one only if it truly does not apply):

### Related Concepts
4-8 closely related ideas, methods or results the guide does not mention. Explain each in 2-4 sentences
and say how it connects to the guide's content.

### Deeper Explanations
2-4 points from the guide that are usually explained in more depth elsewhere (a derivation, a proof
sketch, a geometric picture, a limitation). Name the point and give the deeper explanation.

### Real-World Applications
3-6 concrete places this topic is used in practice, with a sentence on how.

### Where This Leads
What students usually learn next after this topic and why it builds on it.

### Further Reading
3-5 well-known, real textbooks or courses on this topic (author and title only, no URLs).
Only list resources you are certain exist.

Start directly with the first ### heading. Do not add a ## heading, introduction or conclusion.

--- STUDY GUIDE ---
{notes}
"""

CHAT_SYSTEM = """You are a helpful study assistant answering questions about the document "{title}".
Answer ONLY using the excerpts provided below. Cite sources inline like [Page 3] or [Slide 5].
If the answer is not in the excerpts, say clearly that the document doesn't seem to cover it, then (separately, labelled "General knowledge:") you may give a brief general explanation.
Explain things simply, like a good tutor, using examples when helpful. Use Markdown.

--- DOCUMENT OVERVIEW ---
{overview}

--- RELEVANT EXCERPTS ---
{context}
"""
