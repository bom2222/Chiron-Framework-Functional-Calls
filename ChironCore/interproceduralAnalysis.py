#!/usr/bin/python3

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import ChironAST.ChironAST as ChironAST


@dataclass
class PassResult:
    name: str
    summary: str
    details: List[str]


class InterproceduralPass:
    name = "InterproceduralPass"

    def run(self, programIR, callGraph, analysisState):
        raise NotImplementedError


class ReachableFunctionsPass(InterproceduralPass):
    name = "ReachableFunctionsPass"

    def run(self, programIR, callGraph, analysisState):
        visited: Set[str] = set()
        stack = ["__main__"]

        while stack:
            node = stack.pop()
            if node in visited:
                continue
            visited.add(node)
            for succ in callGraph.successors(node):
                if succ not in visited:
                    stack.append(succ)

        reachableFunctions = sorted([f for f in visited if f != "__main__"])
        analysisState["reachableFunctions"] = set(reachableFunctions)

        return PassResult(
            name=self.name,
            summary=f"Reachable functions from __main__: {len(reachableFunctions)}",
            details=reachableFunctions,
        )


class UnusedFunctionsPass(InterproceduralPass):
    name = "UnusedFunctionsPass"

    def run(self, programIR, callGraph, analysisState):
        declaredFunctions = set((programIR.functions or {}).keys())
        reachableFunctions = analysisState.get("reachableFunctions", set())
        unusedFunctions = sorted(declaredFunctions - set(reachableFunctions))

        analysisState["unusedFunctions"] = set(unusedFunctions)
        details = unusedFunctions if unusedFunctions else ["No unused functions detected."]

        return PassResult(
            name=self.name,
            summary=f"Unused function count: {len(unusedFunctions)}",
            details=details,
        )


class ConstantValueAnalysisPass(InterproceduralPass):
    name = "ConstantValueAnalysisPass"

    def _var_name(self, varObj):
        return varObj.varname if isinstance(varObj, ChironAST.Var) else str(varObj)

    def _is_internal_loop_var(self, varName):
        return "__rep_counter_" in varName

    def _eval_expr(self, expr, env):
        if isinstance(expr, ChironAST.Num):
            return expr.val
        if isinstance(expr, ChironAST.Var):
            return env.get(expr.varname)
        if isinstance(expr, ChironAST.UMinus):
            val = self._eval_expr(expr.expr, env)
            return -val if val is not None else None
        if isinstance(expr, ChironAST.Sum):
            lval = self._eval_expr(expr.lexpr, env)
            rval = self._eval_expr(expr.rexpr, env)
            return (lval + rval) if lval is not None and rval is not None else None
        if isinstance(expr, ChironAST.Diff):
            lval = self._eval_expr(expr.lexpr, env)
            rval = self._eval_expr(expr.rexpr, env)
            return (lval - rval) if lval is not None and rval is not None else None
        if isinstance(expr, ChironAST.Mult):
            lval = self._eval_expr(expr.lexpr, env)
            rval = self._eval_expr(expr.rexpr, env)
            return (lval * rval) if lval is not None and rval is not None else None
        if isinstance(expr, ChironAST.Div):
            lval = self._eval_expr(expr.lexpr, env)
            rval = self._eval_expr(expr.rexpr, env)
            if lval is None or rval is None or rval == 0:
                return None
            return lval // rval
        return None

    def _rewrite_expr(self, expr, env):
        if isinstance(expr, ChironAST.Var):
            if expr.varname in env:
                return ChironAST.Num(env[expr.varname])
            return expr

        if isinstance(expr, (ChironAST.Num, ChironAST.BoolTrue, ChironAST.BoolFalse, ChironAST.PenStatus)):
            return expr

        if isinstance(expr, ChironAST.UMinus):
            rewritten = ChironAST.UMinus(self._rewrite_expr(expr.expr, env))
            folded = self._eval_expr(rewritten, env)
            return ChironAST.Num(folded) if folded is not None else rewritten

        if isinstance(expr, ChironAST.BinArithOp):
            rewritten = type(expr)(
                self._rewrite_expr(expr.lexpr, env),
                self._rewrite_expr(expr.rexpr, env),
            )
            folded = self._eval_expr(rewritten, env)
            return ChironAST.Num(folded) if folded is not None else rewritten

        if isinstance(expr, ChironAST.BinCondOp):
            return type(expr)(
                self._rewrite_expr(expr.lexpr, env),
                self._rewrite_expr(expr.rexpr, env),
            )

        if isinstance(expr, ChironAST.NOT):
            return ChironAST.NOT(self._rewrite_expr(expr.expr, env))

        return expr

    def _read_vars_expr(self, expr):
        if expr is None:
            return set()
        if isinstance(expr, ChironAST.Var):
            return {expr.varname}
        if isinstance(expr, ChironAST.Num):
            return set()
        if isinstance(expr, ChironAST.UMinus):
            return self._read_vars_expr(expr.expr)
        if isinstance(expr, ChironAST.BinArithOp) or isinstance(expr, ChironAST.BinCondOp):
            return self._read_vars_expr(expr.lexpr).union(self._read_vars_expr(expr.rexpr))
        if isinstance(expr, ChironAST.NOT):
            return self._read_vars_expr(expr.expr)
        return set()

    def _drop_dead_assignments_as_nop(self, irList):
        rewritten = [None] * len(irList)
        liveVars = set()
        removedAssignments = 0

        for idx in range(len(irList) - 1, -1, -1):
            instruction, jump = irList[idx]

            if isinstance(instruction, ChironAST.AssignmentCommand):
                lhsName = self._var_name(instruction.lvar)
                rhsUses = self._read_vars_expr(instruction.rexpr)

                if (not self._is_internal_loop_var(lhsName)) and lhsName not in liveVars:
                    rewritten[idx] = (ChironAST.NoOpCommand(), jump)
                    removedAssignments += 1
                    continue

                liveVars.discard(lhsName)
                liveVars.update(rhsUses)
                rewritten[idx] = (instruction, jump)
                continue

            if isinstance(instruction, ChironAST.MoveCommand):
                liveVars.update(self._read_vars_expr(instruction.expr))
            elif isinstance(instruction, ChironAST.GotoCommand):
                liveVars.update(self._read_vars_expr(instruction.xcor))
                liveVars.update(self._read_vars_expr(instruction.ycor))
            elif isinstance(instruction, ChironAST.ConditionCommand):
                liveVars.update(self._read_vars_expr(instruction.cond))
            elif isinstance(instruction, ChironAST.CallCommand):
                for arg in instruction.args:
                    liveVars.update(self._read_vars_expr(arg))
            elif isinstance(instruction, ChironAST.ReturnCommand):
                liveVars.update(self._read_vars_expr(instruction.rexpr))

            rewritten[idx] = (instruction, jump)

        return rewritten, removedAssignments

    def _scan_callsite_constant_args(self, irList, localEnv, callArgCandidates):
        for item in irList or []:
            if not item:
                continue
            instruction = item[0]

            if isinstance(instruction, ChironAST.AssignmentCommand):
                name = self._var_name(instruction.lvar)
                if self._is_internal_loop_var(name):
                    localEnv.pop(name, None)
                    continue
                rhs = self._rewrite_expr(instruction.rexpr, localEnv)
                constVal = self._eval_expr(rhs, localEnv)
                if constVal is None:
                    localEnv.pop(name, None)
                else:
                    localEnv[name] = constVal
                continue

            if isinstance(instruction, ChironAST.CallCommand):
                callInfo = callArgCandidates.setdefault(instruction.fname, [])
                argConstants = []
                for arg in instruction.args:
                    argConstants.append(self._eval_expr(self._rewrite_expr(arg, localEnv), localEnv))
                callInfo.append(argConstants)

    def _merge_constant_params(self, functionIR, observedCalls):
        if not observedCalls:
            return {}

        merged = {}
        for paramIndex, paramName in enumerate(functionIR.params):
            candidate: Optional[int] = None
            consistent = True

            for args in observedCalls:
                if paramIndex >= len(args):
                    consistent = False
                    break
                if args[paramIndex] is None:
                    consistent = False
                    break
                if candidate is None:
                    candidate = args[paramIndex]
                elif candidate != args[paramIndex]:
                    consistent = False
                    break

            if consistent and candidate is not None:
                merged[paramName] = candidate

        return merged

    def _rewrite_ir(self, irList, startEnv):
        env = dict(startEnv)
        rewrittenIR = []
        simplifiedAssignments = 0

        for item in irList or []:
            if not item:
                continue

            instruction, jump = item

            if isinstance(instruction, ChironAST.AssignmentCommand):
                lhsName = self._var_name(instruction.lvar)
                if self._is_internal_loop_var(lhsName):
                    env.pop(lhsName, None)
                    rewrittenIR.append((instruction, jump))
                    continue

                oldRHS = str(instruction.rexpr)
                rhs = self._rewrite_expr(instruction.rexpr, env)
                rewritten = ChironAST.AssignmentCommand(instruction.lvar, rhs)
                constVal = self._eval_expr(rhs, env)
                if constVal is None:
                    env.pop(lhsName, None)
                else:
                    env[lhsName] = constVal
                if str(rhs) != oldRHS:
                    simplifiedAssignments += 1
                rewrittenIR.append((rewritten, jump))
                continue

            if isinstance(instruction, ChironAST.MoveCommand):
                rewrittenIR.append((ChironAST.MoveCommand(instruction.direction, self._rewrite_expr(instruction.expr, env)), jump))
                continue

            if isinstance(instruction, ChironAST.GotoCommand):
                rewrittenIR.append((ChironAST.GotoCommand(self._rewrite_expr(instruction.xcor, env), self._rewrite_expr(instruction.ycor, env)), jump))
                continue

            if isinstance(instruction, ChironAST.ConditionCommand):
                # Skip rewriting conditions to avoid unsound loop-condition changes
                # in this linear (CFG-insensitive) pass.
                rewrittenIR.append((instruction, jump))
                continue

            if isinstance(instruction, ChironAST.CallCommand):
                rewrittenArgs = [self._rewrite_expr(arg, env) for arg in instruction.args]
                rewrittenIR.append((ChironAST.CallCommand(instruction.fname, rewrittenArgs), jump))
                continue

            if isinstance(instruction, ChironAST.ReturnCommand):
                rexpr = None if instruction.rexpr is None else self._rewrite_expr(instruction.rexpr, env)
                rewrittenIR.append((ChironAST.ReturnCommand(rexpr), jump))
                continue

            rewrittenIR.append((instruction, jump))

        return rewrittenIR, simplifiedAssignments

    def run(self, programIR, callGraph, analysisState):
        functions = programIR.functions or {}

        callArgCandidates = {}
        self._scan_callsite_constant_args(programIR.mainIR, {}, callArgCandidates)
        for funcIR in functions.values():
            self._scan_callsite_constant_args(funcIR.bodyIR, {}, callArgCandidates)

        inferredParams = {}
        for fname, funcIR in functions.items():
            observedCalls = callArgCandidates.get(fname, [])
            inferredParams[fname] = self._merge_constant_params(funcIR, observedCalls)

        simplifiedAssignments = 0
        removedAssignments = 0

        mainRewritten, mainSimple = self._rewrite_ir(programIR.mainIR, {})
        mainFinal, mainRemoved = self._drop_dead_assignments_as_nop(mainRewritten)
        programIR.mainIR = mainFinal
        simplifiedAssignments += mainSimple
        removedAssignments += mainRemoved

        rewrittenFunctions = {}
        for fname, funcIR in functions.items():
            startEnv = inferredParams.get(fname, {})
            finalBody, simple = self._rewrite_ir(funcIR.bodyIR, startEnv)
            finalBody, removed = self._drop_dead_assignments_as_nop(finalBody)
            funcIR.bodyIR = finalBody
            rewrittenFunctions[fname] = funcIR
            simplifiedAssignments += simple
            removedAssignments += removed

        programIR.functions = rewrittenFunctions

        analysisState["constantParamInference"] = inferredParams
        analysisState["simplifiedAssignments"] = simplifiedAssignments
        analysisState["removedAssignments"] = removedAssignments

        details = []
        for fname in sorted(inferredParams.keys()):
            mapping = inferredParams[fname]
            if mapping:
                details.append(f"{fname}: {mapping}")

        if not details:
            details = ["No inter-procedural constant parameter bindings inferred."]

        details.append(f"Assignments simplified (RHS rewritten/folded): {simplifiedAssignments}")
        details.append(f"Dead assignments converted to NOP: {removedAssignments}")

        return PassResult(
            name=self.name,
            summary="Constant propagation/folding applied on main and function IR.",
            details=details,
        )


class InterproceduralAnalysisRunner:
    def __init__(self):
        self.passes = [
            ReachableFunctionsPass(),
            UnusedFunctionsPass(),
            ConstantValueAnalysisPass(),
        ]

    def run(self, irHandler):
        programIR = irHandler.programIR
        callGraph = irHandler.callGraph

        if programIR is None or callGraph is None:
            return []

        results = []
        state: Dict[str, object] = {}
        for passInstance in self.passes:
            results.append(passInstance.run(programIR, callGraph, state))

        irHandler.setProgramIR(programIR)
        irHandler.setIR(programIR.mainIR)
        return results


def runInterproceduralAnalysis(irHandler):
    runner = InterproceduralAnalysisRunner()
    return runner.run(irHandler)
