to drawSquare(:side) [
    repeat 4 [
        forward :side
        right 90
    ]
]

to moveAndDraw(:x, :y, :len) [
    goto(:x, :y)
    drawSquare(:len)
]

moveAndDraw(50, 50, 40)
moveAndDraw(-50, -50, 20)
