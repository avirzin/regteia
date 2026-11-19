# 0003. `vigencia_em`: status on a date from recorded events

Date: 2026-11-18. Status: accepted. Roadmap step 7.

## Context

`vigencia_em(ref, data)` answers whether a norm or a Dispositivo applied on a date, past or future. The graph has
status over time (dated edges) but not text over time: each Dispositivo holds the portal's latest wording only. The
dates are incomplete: about a third of the revoked norms' REVOGA edges carry `desde`, article-level edges carry
`a_partir_de` only when the entry states one, and a few amending norms are stubs with no date.

## Decision

1. **Where each date comes from.**
   - A norm starts on its own `data`. We don't read "entra em vigor" clauses, and the answer says so for dates
     close to the norm's date.
   - A whole-norm revocation is a REVOGA edge, dated by its `desde` or else by the revoking norm's `data`.
   - An article-level change is an `ALTERA` edge from `atualizacoes`, or a target stored as `ausente` on the
     entry. Its date is `a_partir_de`, or else the amending norm's `data`.
   - Each event records which source was used (`origem_data`).
2. **Several revocations: the earliest dated one counts.** Later ones revoke what was already revoked, as
   consolidation acts do. A revocation dated before the norm itself is a source error: it is reported and treated as
   undated.
3. **`estado` is authoritative for today.** A norm marked revoked is revoked on any date from today on, even without
   a dated edge. A revocation dated in the past on a norm the portal shows in force is reported, not applied. A
   revocation dated in the future applies from its date.
4. **No date, no guess.** Before the earliest known revocation, if any undated revocation exists, the answer is
   `indeterminada`. The same holds for a Dispositivo shown revoked whose history has no dated revocation, and for a
   whole-article inclusion or revocation with no date.
5. **Article scope.**
   - Only changes to the whole article (no `detalhe`) create or end it. "Inclusão: art. 5º, inciso IV" changes
     art. 5, it doesn't create it.
   - An article with an inclusion doesn't exist before its first inclusion.
   - An article inherits the norm's status when the norm itself isn't in force.
   - To support this rule, the parser stores `ausentes_detalhe` (parser version 2).
6. **Text.** For a Dispositivo in force, `texto_na_data` is one of:
   - `armazenado`: no change to it takes effect after the date, so the stored wording is that date's. It is
     returned.
   - `desconhecido`: some change takes effect after the date. The later changes are listed, and no text is
     returned.
   - `sem_texto`: the article is not in force, or it is in the history but not yet in the portal's text.

   Entries of the norm that weren't read down to the article and may postdate the date are flagged in a note.

## Consequences

The answer can be `indeterminada`. That is the honest result when the source has no date. Every answer lists the
events it used, with their dates and where each date came from, so a reader can check the answer against the
official source. `vigencia_em` never returns an earlier wording. That needs text versions (upstream's git history),
which is a later step.
