import sys

class P(DistProcess):
    def setup(self, s:set, nrequests:int):  # s is set of all other
        # processes
        self.s = s
        self.nrequests = nrequests
        self.q = set()

    def receive(msg= ('request', c2, p)):
        q.add(('request', c2, p))
        send(('ack', logical_clock(), self.id), to= p)

    def receive(msg= ('release', _, p)):
#        q.remove(('request', _, p))  # pattern matching needed for _
#        q.remove(anyof(setof(('request', c, p), ('request', c, _p) in q)))
        for x in setof(('request', c, p), ('request', c, _p) in q):
            q.remove(x); break
#        for ('request', c, _p) in q: q.remove('request', c, p); break
#        for (tag, c, p2) in q:
#            if tag == 'request' and p2 == p:
#                q.remove((tag, c, p2)); break

    def run(self, yp, vstate):
        newprocesses = set()
        # done is initially false. it is set to true when execution has
        # reached the next yield point or the end of the method.
        done = False

        if yp != 'start':
            # Restore local state
            (task, ) = vstate

        if yp == 'start':
            def task():
                output('in cs')
        # for i in range(nrequests):
        loop_iter = iter(range(nrequests))
        if yp == 'request' and not done:
            try:
                i = next(loop_iter)
                c = logical_clock()
                send(('request', c, self.id), to= s)
                q.add(('request', c, self.id))
                yp = 'label1'
            except StopIteration:
                send(('done', self.id), to= s)
                yp = 'label2'

        if yp == 'label1' and not done:
            # await(each(('request', c2, p) in q,
            #            has= (c2, p)==(c, self.id) or (c, self.id) < (c2, p)) and
            #       each(p in s, has= some(received(('ack', c2, _p)), has=
            #       c2 > c))) 
           p = c2 = None

            def UniversalOpExpr_0():
                nonlocal p, c2
                for (_ConstantPattern0_, c2, p) in self.q:
                    if (_ConstantPattern0_ == 'request'):
                        if (not (((c2, p) == (c, self.id)) or ((c, self.id) < (c2, p)))):
                            return False
                return True
            p = c2 = None

            def UniversalOpExpr_1():
                nonlocal p, c2
                for p in self.s:

                    def ExistentialOpExpr_2(p):
                        nonlocal c2
                        for (_, _, (_ConstantPattern16_, c2, _BoundPattern18_)) in self._PReceivedEvent_0:
                            if (_ConstantPattern16_ == 'ack'):
                                if (_BoundPattern18_ == p):
                                    if (c2 > c):
                                        return True
                        return False
                    if (not ExistentialOpExpr_2(p=p)):
                        return False
                return True
            if (UniversalOpExpr_0() and UniversalOpExpr_1()):
                _st_label_10 += 1

            -- critical_section
            task()
            -- release
            q.remove(('request', c, self.id))
            send(('release', logical_clock(), self.id), to= s)

        send(('done', self.id), to= s)
        await(each(p in s, has= received(('done', p))))
        output('terminating')

def scheduler(processes):
    """
    :type processes: set
    """
    state = {p : ('start', None) for p in processes}

    while len(processes) > 0:
        p = nondetChoose(processes)
        (yp, vstate, newprocesses) = p.run(p.state[0], p.state[1])
        if (yp == 'end'):
            processes.remove(p)
            del state[p]
        else:
            state[p] = (yp, vstate)
            p.handle(yp)
        processes.update(newprocesses)

def main():
    newprocesses = set()

    nprocs = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    nrequests = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    ps = {P() for _ in range(nprocs)} # new(P, num= nprocs)
    newprocesses.update(ps)
    for p in ps:
        p.setup(ps-{p}, nrequests)
    # start(ps)
    for p in ps:
        p.start()

    scheduler(newprocesses)


# Non-determinism support routines
import random
random.seed()

def nondetChoose(collection):
    if isinstance(collection, set):
        return random.sample(collection, 1)[0]
    else:
        return random.choice(collection)
