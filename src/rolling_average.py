class ROLLINGAVERAGE:
    def __init__(self, **kwargs):
        samples = kwargs.get('samples', 5)
        self.holder = [None] * samples
        self.index = 0

    def submit(self, value):
        self.holder[self.index] = value
        if self.index < len(self.holder) - 1:
            self.index += 1
        else:
            self.index = 0

    def compute_avg(self):
        samples = 0
        total = 0
        for i in self.holder:
            if i is not None:
                samples += 1
                total += i
        if samples > 0:
            return (total / samples)
        else:
            return None


