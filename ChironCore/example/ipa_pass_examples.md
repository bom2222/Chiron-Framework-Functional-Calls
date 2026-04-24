# Inter-procedural analysis pass examples

The following examples exercise `-ipa/--interproceduralAnalysis` and the new run-mode comparison flags.

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

## 2) Constant propagation + updated IR

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
  - Assignments simplified (RHS rewritten/folded): 3

== Updated IR after inter-procedural passes ==
...
========== Updated Function IR : drawOffset(:start) ==========
...
[L0] :len = 18 [1]
[L1] forward 18 [1]
[L2] :step = 20 [1]
[L3] right 20 [1]
```

## 3) Runtime comparison mode for testers

Normal run (baseline):

```bash
uv run python chiron.py -r example/ipa_constant_values.tl -d '{":base": 10}'
```

IPA run (passes first, then execute):

```bash
uv run python chiron.py -ipa_run example/ipa_constant_values.tl -d '{":base": 10}'
```

Both runs print the same runtime metrics format for comparison:

```text
== Normal Run Stats ==
Total instructions executed (including function bodies): ...
Execution time (seconds): ...

== IPA Run Stats ==
Total instructions executed (including function bodies): ...
Execution time (seconds): ...
```
