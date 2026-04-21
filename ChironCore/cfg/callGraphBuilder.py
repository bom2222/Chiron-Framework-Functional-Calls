#!/usr/bin/python3

import networkx as nx
import ChironAST.ChironAST as ChironAST


def _scanCalls(irList):
    callees = set()
    for item in irList:
        if isinstance(item[0], ChironAST.CallCommand):
            callees.add(item[0].fname)
    return callees


def buildCallGraph(programIR):
    callGraph = nx.DiGraph()
    callGraph.add_node("__main__")
    for fname in programIR.functions.keys():
        callGraph.add_node(fname)

    for callee in _scanCalls(programIR.mainIR):
        callGraph.add_edge("__main__", callee)

    for fname, funcIR in programIR.functions.items():
        for callee in _scanCalls(funcIR.bodyIR):
            callGraph.add_edge(fname, callee)

    return callGraph
