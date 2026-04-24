to drawSquare(:side) [
    repeat 4 [
        forward :side
        right 90
    ]
]

to drawPentagon(:side)[
    repeat 5 [
        forward :side
        right 72
    ]
]

to moveAndDraw(:x, :y, :len) [
    goto(:x, :y)
    drawSquare(:len)
    forward :len
    drawPentagon(:len)
]

moveAndDraw(50, 50, 40)
moveAndDraw(-50, -50, 40)
