to drawStep(:len) [
    forward :len
    right 90
]

to drawCorner(:len) [
    drawStep(:len)
    drawStep(:len)
]

to neverCalled(:size) [
    forward :size
]

drawCorner(15)
