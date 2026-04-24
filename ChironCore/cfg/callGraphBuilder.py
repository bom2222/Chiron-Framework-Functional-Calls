#!/usr/bin/python3

import networkx as nx
import ChironAST.ChironAST as ChironAST


def _scanCalls(irList):
    callees = set()
    for item in irList:
        if not item:
            continue
        instr = item[0]
        if isinstance(instr, ChironAST.CallCommand):
            callees.add(instr.fname)
    return sorted(callees)


def buildCallGraph(programIR):
    if programIR is None:
        raise ValueError("programIR cannot be None")

    callGraph = nx.DiGraph()
    callGraph.add_node("__main__")

    functions = getattr(programIR, "functions", {}) or {}
    mainIR = getattr(programIR, "mainIR", []) or []

    for fname in sorted(functions.keys()):
        callGraph.add_node(fname)

    declaredFunctionNames = set(functions.keys())

    for callee in _scanCalls(mainIR):
        if callee not in declaredFunctionNames:
            raise ValueError(f"Call graph generation failed. Undefined function call in __main__: '{callee}'.")
        callGraph.add_edge("__main__", callee)

    for fname in sorted(functions.keys()):
        funcIR = functions[fname]
        for callee in _scanCalls(getattr(funcIR, "bodyIR", []) or []):
            if callee not in declaredFunctionNames:
                raise ValueError(f"Call graph generation failed. Undefined function call in '{fname}': '{callee}'.")
            callGraph.add_edge(fname, callee)

    return callGraph
