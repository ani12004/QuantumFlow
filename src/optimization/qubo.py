"""Two-cycle one-hot green-split QUBO with a deterministic fluid queue surrogate."""
from dataclasses import dataclass
import itertools
import numpy as np

APPROACHES=('N','S','E','W')

def phase_schedule(ns_green,config):
    yellow=config['yellow_seconds'];red=config['all_red_seconds']
    available=config['cycle_seconds']-2*(yellow+red)
    ew_green=available-ns_green
    low=config['minimum_green_seconds'];high=config['maximum_green_seconds']
    if not (low<=ns_green<=high and low<=ew_green<=high): raise ValueError('Green bounds violated')
    return [('NS',ns_green),('NS_yellow',yellow),('all_red',red),('EW',ew_green),('EW_yellow',yellow),('all_red',red)]

def fluid_cycle(queue,arrivals,ns_green,config):
    """Queues in veh, arrivals/s, service/s. Area is veh*s; no service in clearance."""
    q=np.asarray(queue,dtype=float).copy();a=np.asarray(arrivals,dtype=float)
    if q.shape!=(4,) or a.shape!=(4,) or np.any(q<0) or np.any(a<0) or not np.all(np.isfinite(q+a)):
        raise ValueError('Four finite nonnegative approach queues and rates required')
    delay=0.;sat=config['saturation_flow_veh_per_second_per_lane']
    for phase,duration in phase_schedule(ns_green,config):
        service=np.array([sat,sat,0,0] if phase=='NS' else [0,0,sat,sat] if phase=='EW' else [0,0,0,0])
        for _ in range(int(duration)):
            next_q=np.maximum(0,q+a-service)
            delay+=float(np.sum((q+next_q)*.5));q=next_q
    return delay,q

@dataclass
class Qubo:
    matrix: np.ndarray  # Upper triangular: E(x)=offset+x.T@matrix@x.
    offset: float
    options: list
    penalty: float
    feasible_costs: np.ndarray

    @property
    def n(self):return len(self.matrix)

    def energy(self,bits):
        x=np.asarray(bits,dtype=int)
        return float(self.offset+x@self.matrix@x)

    def feasible(self,bits):
        x=np.asarray(bits);m=len(self.options)
        return x.shape==(2*m,) and np.isin(x,[0,1]).all() and x[:m].sum()==1 and x[m:].sum()==1

    def decode(self,bits):
        if not self.feasible(bits):raise ValueError('Infeasible one-hot schedule')
        m=len(self.options)
        return [self.options[int(np.argmax(bits[:m]))],self.options[int(np.argmax(bits[m:]))]]

    def all_energies(self):
        if self.n>16:raise ValueError('Demo exact/statevector implementation limited to 16 qubits')
        basis=np.arange(2**self.n,dtype=np.uint32)
        bits=((basis[:,None]>>np.arange(self.n))&1).astype(np.int8)
        values=self.offset+np.einsum('bi,ij,bj->b',bits,self.matrix,bits,optimize=True)
        return bits,values

    def ising(self):
        h=-np.diag(self.matrix)/2;couplings=[];offset=self.offset+np.trace(self.matrix)/2
        for i,j in itertools.combinations(range(self.n),2):
            weight=float(self.matrix[i,j])/4
            if weight:
                h[i]-=weight;h[j]-=weight;offset+=weight;couplings.append((i,j,weight))
        return float(offset),h,couplings

def build_qubo(queue,arrival_rates,config):
    if config['planning_cycles']!=2:raise ValueError('This pairwise surrogate supports exactly two planning cycles')
    options=list(config['green_options_ns_seconds']);m=len(options)
    first=[];second=np.zeros((m,m));terminal=config['terminal_queue_weight_seconds_per_vehicle']
    for i,green in enumerate(options):
        delay,q=fluid_cycle(queue,arrival_rates,green,config);first.append(delay)
        for j,next_green in enumerate(options):
            next_delay,terminal_q=fluid_cycle(q,arrival_rates,next_green,config)
            second[i,j]=next_delay+terminal*float(terminal_q@terminal_q)+config['split_change_weight_vehicle_seconds_per_second_squared']*(green-next_green)**2
    costs=np.asarray(first)[:,None]+second
    # All physical terms >=0. Any infeasible one-hot block costs >=A;
    # A > largest feasible cost makes every global minimizer feasible.
    penalty=float(costs.max()+1)
    matrix=np.zeros((2*m,2*m))
    for block in range(2):
        for i in range(m):
            matrix[block*m+i,block*m+i]=-penalty+(first[i] if block==0 else 0)
        for i,j in itertools.combinations(range(m),2):matrix[block*m+i,block*m+j]=2*penalty
    for i in range(m):
        for j in range(m):matrix[i,m+j]=second[i,j]
    return Qubo(matrix,2*penalty,options,penalty,costs)

def solve_exact(qubo):
    bits,energy=qubo.all_energies();index=int(np.argmin(energy));chosen=bits[index]
    if not qubo.feasible(chosen):raise AssertionError('Penalty failed to ensure feasibility')
    return {'bits':chosen.tolist(),'energy':float(energy[index]),'greens_ns_seconds':qubo.decode(chosen),'solver':'exact_enumeration'}
