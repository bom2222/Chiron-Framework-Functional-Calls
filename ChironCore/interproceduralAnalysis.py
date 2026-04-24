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

    def _scan_callsite_constant_args(self, irList, localEnv, callArgCandidates):
        for item in irList or []:
            if not item:
                continue
            instruction = item[0]

            if isinstance(instruction, ChironAST.AssignmentCommand):
                name = self._var_name(instruction.lvar)
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

        for item in irList or []:
            if not item:
                continue

            instruction, jump = item

            if isinstance(instruction, ChironAST.AssignmentCommand):
                rhs = self._rewrite_expr(instruction.rexpr, env)
                rewritten = ChironAST.AssignmentCommand(instruction.lvar, rhs)
                lhsName = self._var_name(instruction.lvar)
                constVal = self._eval_expr(rhs, env)
                if constVal is None:
                    env.pop(lhsName, None)
                else:
                    env[lhsName] = constVal
                rewrittenIR.append((rewritten, jump))
                continue

            if isinstance(instruction, ChironAST.MoveCommand):
                rewrittenIR.append((ChironAST.MoveCommand(instruction.direction, self._rewrite_expr(instruction.expr, env)), jump))
                continue

            if isinstance(instruction, ChironAST.GotoCommand):
                rewrittenIR.append((ChironAST.GotoCommand(self._rewrite_expr(instruction.xcor, env), self._rewrite_expr(instruction.ycor, env)), jump))
                continue

            if isinstance(instruction, ChironAST.ConditionCommand):
                rewrittenIR.append((ChironAST.ConditionCommand(self._rewrite_expr(instruction.cond, env)), jump))
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

        return rewrittenIR

    def run(self, programIR, callGraph, analysisState):
        functions = programIR.functions or {}

        # Collect observed constant arguments per callsite across main and functions.
        callArgCandidates = {}
        self._scan_callsite_constant_args(programIR.mainIR, {}, callArgCandidates)
        for funcIR in functions.values():
            self._scan_callsite_constant_args(funcIR.bodyIR, {}, callArgCandidates)

        inferredParams = {}
        for fname, funcIR in functions.items():
            observedCalls = callArgCandidates.get(fname, [])
            inferredParams[fname] = self._merge_constant_params(funcIR, observedCalls)

        # Rewrite main IR and function IR in place.
        programIR.mainIR = self._rewrite_ir(programIR.mainIR, {})

        rewrittenFunctions = {}
        foldedAssignments = 0
        for fname, funcIR in functions.items():
            startEnv = inferredParams.get(fname, {})
            before = funcIR.bodyIR
            after = self._rewrite_ir(funcIR.bodyIR, startEnv)
            funcIR.bodyIR = after
            rewrittenFunctions[fname] = funcIR

            for (oldInst, _), (newInst, _) in zip(before, after):
                if isinstance(oldInst, ChironAST.AssignmentCommand) and str(oldInst.rexpr) != str(newInst.rexpr):
                    foldedAssignments += 1

        programIR.functions = rewrittenFunctions

        analysisState["constantParamInference"] = inferredParams
        details = []
        for fname in sorted(inferredParams.keys()):
            mapping = inferredParams[fname]
            if mapping:
                details.append(f"{fname}: {mapping}")

        if not details:
            details = ["No inter-procedural constant parameter bindings inferred."]

        details.append(f"Assignments simplified: {foldedAssignments}")

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
