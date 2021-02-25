import random
import multiprocessing as m
import time

class Pineapples:
	def __init__(self):
		self.pq = m.JoinableQueue()

	def sing(self):
		s = m.current_process().name \
			+ ": I have a "
		while True:
			pa, pn = self.pq.get()
			if pa or pn:
				print(f"{s}{pa}{pn}!")
			if pa and pn:
				break
			self.pq.task_done()

	def rand(self):
		return bool(random.getrandbits(1))
		
	def run(self):
		for _ in range(m.cpu_count()):
			p = m.Process(target=self.sing)
			p.start()
		
		while True:
			pa = "pineapple" \
				if self.rand() else ""
			pn = "pen" \
				if self.rand() else ""
			self.pq.put((pa, pn))
			time.sleep(1)

if __name__ == "__main__":
	p = Pineapples()
	p.run()