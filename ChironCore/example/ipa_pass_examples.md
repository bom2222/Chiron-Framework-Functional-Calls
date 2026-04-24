# Inter-procedural analysis pass examples

The following examples exercise `-ipa/--interproceduralAnalysis`.

Passes included now:
- `ReachableFunctionsPass`
- `UnusedFunctionsPass`
- `ConstantValueAnalysisPass`

## 1) Unused-function detection

Program: `example/ipa_unused_function.tl`

Run:

```bash
uv run python chiron.py -ipa example/ipa_unused_function.tl
```

Expected highlights:

```text
[PASS] ReachableFunctionsPass
  Summary: Reachable functions from __main__: 2
  - drawCorner
  - drawStep
[PASS] UnusedFunctionsPass
  Summary: Unused function count: 1
  - neverCalled
```

## 2) Clean call graph + constant analysis

Program: `example/ipa_clean_program.tl`

Run:

```bash
uv run python chiron.py -ipa example/ipa_clean_program.tl
```

Expected highlights:

```text
[PASS] ReachableFunctionsPass
  Summary: Reachable functions from __main__: 2
[PASS] UnusedFunctionsPass
  Summary: Unused function count: 0
[PASS] ConstantValueAnalysisPass
  Summary: Constant propagation/folding applied on main and function IR.
  - square: {':len': 20}
  - Instructions skipped in -r (converted to NOP): 2
```

## 3) Inter-procedural constant propagation + updated IR

Program: `example/ipa_constant_values.tl`

Run:

```bash
uv run python chiron.py -ipa example/ipa_constant_values.tl
```

Expected highlights:

```text
[PASS] ConstantValueAnalysisPass
  Summary: Constant propagation/folding applied on main and function IR.
  - drawOffset: {':start': 13}
  - Instructions skipped in -r (converted to NOP): 4

== Updated IR after inter-procedural passes ==
...
========== Updated Function IR : drawOffset(:start) ==========
...
[L0] NOP [1]
[L1] forward 18 [1]
[L2] NOP [1]
[L3] right 20 [1]
```
