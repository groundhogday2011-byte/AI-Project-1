# Phase 2 (Drainage): Owner Decisions

Answers to the five open questions in `handoff_phase2_drainage.md`. These must be settled before step 4 (sizing logic).

**Q1 (answered): The toilet rule.** On **horizontal branches and the building drain**, a 3" pipe carries at most 3 toilets. The 4th toilet makes it 4". This applies at **both ¼" and ⅛" per foot**. At either slope, the pipe size is the larger of two answers: the fixture-unit table for that slope, or the toilet count. So ⅛" is never less strict than ¼". Stacks don't use this rule; they're sized from the fixture-unit table only.

**Q2 (answered): Material.** Size drains by nominal pipe size only. There is no PVC, ABS or cast-iron choice.

**Q3 (answered): Slopes**
- Choices: **¼" per foot (default)** and **⅛" per foot**. No ½".
- ⅛" is allowed only on pipe 3" and larger. If a user picks ⅛" on anything smaller, the calculator flags it and sizes at ¼".
- If the actual pipe is steeper than ¼", use the ¼" result. It is conservative.

**Q4 (answered): Scope of the first version.** Only horizontal branches, stacks and the building drain. Vents and trap arms come later.

**Q5 (answered): Credits.** A drainage calculation uses the same credits as a water calculation, from the same balance and at the same cost per calculation. There's no separate drainage credit or price.
