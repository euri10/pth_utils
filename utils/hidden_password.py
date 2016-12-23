class HiddenPassword(object):
    def __init__(self, password=''):
        self.password = password

    def __str__(self):
        return '*' * 4
