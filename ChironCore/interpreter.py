
from ChironAST import ChironAST
from ChironHooks import Chironhooks
import turtle

Release="Chiron v5.3"

def addContext(s):
    return str(s).strip().replace(":", "self.prg.")

class Interpreter:
    # Turtle program should not contain variable with names "ir", "pc", "t_screen"
    ir = None
    pc = None
    t_screen = None
    trtl = None

    def __init__(self, irHandler, params):
        self.ir = irHandler.ir
        self.programIR = irHandler.programIR
        self.cfg = irHandler.cfg
        self.pc = 0
        self.t_screen = turtle.getscreen()
        self.trtl = turtle.Turtle()
        self.trtl.shape("turtle")
        self.trtl.color("blue", "yellow")
        self.trtl.fillcolor("green")
        self.trtl.begin_fill()
        self.trtl.pensize(4)
        self.trtl.speed(1) # TODO: Make it user friendly

        if params is not None:
            self.args = params
        else:
            self.args = None

        turtle.title(Release)
        turtle.bgcolor("white")
        turtle.hideturtle()

    def handleAssignment(self, stmt,tgt):
        raise NotImplementedError('Assignments are not handled!')

    def handleCondition(self, stmt, tgt):
        raise NotImplementedError('Conditions are not handled!')

    def handleMove(self, stmt, tgt):
        raise NotImplementedError('Moves are not handled!')

    def handlePen(self, stmt, tgt):
        raise NotImplementedError('Pens are not handled!')

    def handleGotoCommand(self, stmt, tgt):
        raise NotImplementedError('Gotos are not handled!')

    def handleNoOpCommand(self, stmt, tgt):
        raise NotImplementedError('No-Ops are not handled!')

    def handlePauseCommand(self, stmt, tgt):
        raise NotImplementedError('No-Ops are not handled!')

    def handleCallCommand(self, stmt, tgt):
        raise NotImplementedError('Function calls are not handled!')

    def sanityCheck(self, irInstr):
        stmt, tgt = irInstr
        # if not a condition command, rel. jump can't be anything but 1
        if not isinstance(stmt, ChironAST.ConditionCommand):
            if tgt != 1:
                raise ValueError("Improper relative jump for non-conditional instruction", str(stmt), tgt)
    
    def interpret(self):
        pass

    def initProgramContext(self, params):
        pass

class ProgramContext:
    pass

# TODO: move to a different file
class ConcreteInterpreter(Interpreter):
    # Ref: https://realpython.com/beginners-guide-python-turtle
    cond_eval = None # used as a temporary variable within the embedded program interpreter
    prg = None

    def __init__(self, irHandler, params):
        super().__init__(irHandler, params)
        self.prg = ProgramContext()
        # Hooks Object:
        if self.args is not None and self.args.hooks:
            self.chironhook = Chironhooks.ConcreteChironHooks()
        self.pc = 0
        self.executedInstructions = 0

    def _execStatement(self, stmt, tgt):
        self.executedInstructions += 1
        if isinstance(stmt, ChironAST.AssignmentCommand):
            return self.handleAssignment(stmt, tgt)
        if isinstance(stmt, ChironAST.ConditionCommand):
            return self.handleCondition(stmt, tgt)
        if isinstance(stmt, ChironAST.MoveCommand):
            return self.handleMove(stmt, tgt)
        if isinstance(stmt, ChironAST.PenCommand):
            return self.handlePen(stmt, tgt)
        if isinstance(stmt, ChironAST.GotoCommand):
            return self.handleGotoCommand(stmt, tgt)
        if isinstance(stmt, ChironAST.NoOpCommand):
            return self.handleNoOpCommand(stmt, tgt)
        if isinstance(stmt, ChironAST.CallCommand):
            return self.handleCallCommand(stmt, tgt)
        raise NotImplementedError("Unknown instruction: %s, %s."%(type(stmt), stmt))

    def _interpretFunctionIR(self, irList):
        localPC = 0
        while localPC < len(irList):
            stmt, tgt = irList[localPC]
            self.sanityCheck((stmt, tgt))
            ntgt = self._execStatement(stmt, tgt)
            localPC += ntgt

    def interpret(self):
        print("Program counter : ", self.pc)
        stmt, tgt = self.ir[self.pc]
        print(stmt, stmt.__class__.__name__, tgt)

        self.sanityCheck(self.ir[self.pc])
        ntgt = self._execStatement(stmt, tgt)

        # TODO: handle statement
        self.pc += ntgt

        if self.pc >= len(self.ir):
            # This is the ending of the interpreter.
            self.trtl.write("End, Press ESC", font=("Arial", 15, "bold"))
            if self.args is not None and self.args.hooks:
                self.chironhook.ChironEndHook(self)
            return True
        else:
            return False
    
    def initProgramContext(self, params):
        # This is the starting of the interpreter at setup stage.
        if self.args is not None and self.args.hooks:
            self.chironhook.ChironStartHook(self)
        self.trtl.write("Start", font=("Arial", 15, "bold"))
        for key,val in params.items():
            var = key.replace(":","")
            exec("setattr(self.prg,\"%s\",%s)" % (var, val))
    
    def handleAssignment(self, stmt, tgt):
        print("  Assignment Statement")
        lhs = str(stmt.lvar).replace(":","")
        rhs = addContext(stmt.rexpr)
        exec("setattr(self.prg,\"%s\",%s)" % (lhs,rhs))
        return 1

    def handleCondition(self, stmt, tgt):
        print("  Branch Instruction")
        condstr = addContext(stmt)
        exec("self.cond_eval = %s" % (condstr))
        return 1 if self.cond_eval else tgt

    def handleMove(self, stmt, tgt):
        print("  MoveCommand")
        exec("self.trtl.%s(%s)" % (stmt.direction,addContext(stmt.expr)))
        return 1

    def handleNoOpCommand(self, stmt, tgt):
        print("  No-Op Command")
        return 1

    def handlePen(self, stmt, tgt):
        print("  PenCommand")
        exec("self.trtl.%s()"%(stmt.status))
        return 1

    def handleGotoCommand(self, stmt, tgt):
        print(" GotoCommand")
        xcor = addContext(stmt.xcor)
        ycor = addContext(stmt.ycor)
        exec("self.trtl.goto(%s, %s)" % (xcor, ycor))
        return 1

    def handleCallCommand(self, stmt, tgt):
        print("  CallCommand")
        if self.programIR is None or stmt.fname not in self.programIR.functions:
            raise ValueError(f"Undefined function '{stmt.fname}'.")

        functionIR = self.programIR.functions[stmt.fname]
        argValues = []
        for arg in stmt.args:
            _locals = {"self": self}
            exec("_argval = %s" % addContext(arg), globals(), _locals)
            argValues.append(_locals["_argval"])

        savedParamBindings = {}
        for param, value in zip(functionIR.params, argValues):
            pName = param.replace(":", "")
            hadPreviousValue = hasattr(self.prg, pName)
            prevValue = getattr(self.prg, pName) if hadPreviousValue else None
            savedParamBindings[pName] = (hadPreviousValue, prevValue)
            setattr(self.prg, pName, value)

        self._interpretFunctionIR(functionIR.bodyIR)

        for pName, (hadPreviousValue, prevValue) in savedParamBindings.items():
            if hadPreviousValue:
                setattr(self.prg, pName, prevValue)
            else:
                delattr(self.prg, pName)

        return 1
