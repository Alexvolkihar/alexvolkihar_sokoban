# File de priorité utilisée pour résoudre les niveaux :
class PriorityQueue:
    def  __init__(self):
        self.queue = []

    def push(self, item, priority):
        entry = (priority, item)
        self.queue.append(entry)

    def pop(self):
        x = self.queue.pop(0)
        return x[1]

    def isEmpty(self):
        return len(self.queue) == 0
