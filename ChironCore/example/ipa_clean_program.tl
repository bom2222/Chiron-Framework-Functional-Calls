to line(:len) [
    forward :len
]

to square(:len) [
    repeat 4 [
        line(:len)
        right 90
    ]
]

square(20)
