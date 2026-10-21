"""Prompt templates. Add new study outputs (flashcards, quizzes) here."""

SYSTEM_TUTOR = (
    "You are an expert tutor who turns course material into clear, accurate study notes "
    "for a student preparing for exams. Be faithful to the source: never invent facts. "
    "Keep exact definitions, formulas, dates, names and numbers. Write in Markdown. "
    "Write all mathematics in LaTeX: $...$ for inline maths and $$...$$ on its own line "
    "for important standalone formulas."
)

MAP_NOTES = """Below is part {index} of {total} of the document "{title}".
Each block starts with its source label in square brackets, e.g. [Page 3] or [Slide 5].

Write dense study notes for THIS part only:
- Main ideas and how they connect
- Every definition, formula, rule, date, name or number worth memorising
- Examples, steps of processes, comparisons, and cause/effect relationships
- End each bullet with its source label, e.g. (Page 3)

Use concise bullets grouped under short topic headings (###). No introduction or conclusion.

--- DOCUMENT PART ---
{text}
"""

MERGE_NOTES = """Below are study notes from consecutive parts of the document "{title}".
Merge them into one set of dense notes: remove duplicates, group by topic (### headings), keep every
definition, formula, number and source label. Be concise, but don't drop facts.

--- NOTES ---
{text}
"""

GUIDE_FORMAT = """Use EXACTLY this structure:

## Overview
5-8 sentences: what the document is about, its purpose, and the big picture a student must understand.

## Key Notes
Organised by topic with ### subheadings and concise bullets. Cover every important concept. Use **bold** for key words. Use tables when comparing things.

## Key Terms
A Markdown table: | Term | Definition |

## Likely Exam Points
6-12 bullets of what is most likely to be tested and why it matters (common pitfalls, things easily confused).

## Quick Revision Checklist
A short "- [ ]" checklist of things the student should be able to explain or do after studying.
"""

REDUCE_NOTES = """You have study notes extracted from all parts of the document "{title}".
Merge them into one well-organised study guide. Remove duplicates, group related topics, keep source labels in parentheses.

""" + GUIDE_FORMAT + """
--- NOTES ---
{text}
"""

SINGLE_NOTES = """Below is the full text of the document "{title}".
Each block starts with its source label in square brackets, e.g. [Page 3] or [Slide 5].
Turn it into a well-organised study guide, keeping source labels in parentheses after facts.

""" + GUIDE_FORMAT + """
--- DOCUMENT ---
{text}
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
