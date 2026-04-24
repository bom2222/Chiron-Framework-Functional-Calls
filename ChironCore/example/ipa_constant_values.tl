to drawOffset(:start) [
    :len = :start + 5
    forward :len
    :step = :len + 2
    right :step
]

:base = 10
:offset = :base + 3
drawOffset(:offset)
