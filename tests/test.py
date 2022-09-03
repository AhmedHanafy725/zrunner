from zrunner import skip

def before():
    print("before")

def after():
    print("after")


def test1():
    x = 5
    assert x == 5

def test2():
    x = 4
    assert x == 5

def test3():
    raise Exception("test")

@skip("this skip test")
def test4():
    x = 5
