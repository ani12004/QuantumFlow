"""Actual QAOA unitary simulation, not a quantum-hardware execution.

Statevector order is little endian: bit i corresponds to variable i.
Cost unitary exp(-i gamma H/P); mixer exp(-i beta sum X_i).
Classical optimization minimizes expected penalized energy, without exact-solver hints.
"""
import time
import numpy as np
from scipy.optimize import minimize

def statevector(energies,n,parameters,scale):
    if n>16:raise ValueError('Statevector demo limited to 16 qubits')
    p=len(parameters)//2
    if len(parameters)!=2*p or p<1:raise ValueError('Need p gammas and p betas')
    psi=np.full(2**n,1/np.sqrt(2**n),dtype=complex)
    centered=(np.asarray(energies)-np.min(energies))/scale
    for layer in range(p):
        psi*=np.exp(-1j*parameters[layer]*centered)
        beta=parameters[p+layer];c=np.cos(beta);s=-1j*np.sin(beta)
        for qubit in range(n):
            block=psi.reshape(-1,2,2**qubit);a=block[:,0,:].copy();b=block[:,1,:].copy()
            block[:,0,:]=c*a+s*b;block[:,1,:]=s*a+c*b
    return psi

def solve_qaoa(qubo,config,seed):
    start=time.perf_counter();bits,energies=qubo.all_energies();p=int(config['layers'])
    rng=np.random.default_rng(seed);scale=qubo.penalty
    evaluations=0
    def expected(parameters):
        nonlocal evaluations
        evaluations+=1
        psi=statevector(energies,qubo.n,parameters,scale)
        return float(np.dot(np.abs(psi)**2,energies)/scale)
    best=None;runs=[]
    for _ in range(config['restarts']):
        initial=np.r_[rng.uniform(-np.pi,np.pi,p),rng.uniform(-np.pi/2,np.pi/2,p)]
        result=minimize(expected,initial,method='COBYLA',options={'maxiter':config['max_iterations'],'rhobeg':.5,'tol':1e-4})
        runs.append({'expectation_scaled':float(result.fun),'evaluations':int(result.nfev),'converged':bool(result.success)})
        if best is None or result.fun<best.fun:best=result
    psi=statevector(energies,qubo.n,best.x,scale);probability=np.abs(psi)**2;probability/=probability.sum()
    feasible=np.array([qubo.feasible(x) for x in bits]);shots=int(config['shots'])
    samples=rng.choice(len(bits),size=shots,p=probability)
    valid=samples[feasible[samples]];fallback=len(valid)==0
    if fallback:
        # Explicit fixed-split fallback; never use exact optimum to repair QAOA output.
        middle=len(qubo.options)//2;chosen=np.zeros(qubo.n,dtype=int);chosen[middle]=chosen[middle+len(qubo.options)]=1
        chosen_energy=qubo.energy(chosen)
    else:
        index=int(valid[np.argmin(energies[valid])]);chosen=bits[index];chosen_energy=float(energies[index])
    return {'solver':'qaoa_statevector','backend':'NumPy noiseless statevector on classical CPU','qubits':qubo.n,
          'layers':p,'shots':shots,'seed':seed,'parameters':best.x.tolist(),'energy_scale':scale,
          'expected_energy':float(np.dot(probability,energies)),'sampled_energy':chosen_energy,'energy':chosen_energy,
          'bits':chosen.tolist(),'greens_ns_seconds':qubo.decode(chosen),'feasible_probability':float(probability[feasible].sum()),
          'feasible_shots':len(valid),'fallback_used':fallback,'classical_parameter_evaluations':evaluations,
          'optimizer_runs':runs,'solver_wall_seconds':time.perf_counter()-start}

def qasm(qubo,solution):
    """OpenQASM 2 circuit reproducing the fitted state, up to global phase."""
    _,h,couplings=qubo.ising();n=qubo.n;p=solution['layers'];angles=solution['parameters'];scale=solution['energy_scale']
    lines=['OPENQASM 2.0;','include "qelib1.inc";',f'qreg q[{n}];',f'creg c[{n}];']
    lines += [f'h q[{i}];' for i in range(n)]
    for layer in range(p):
        gamma=angles[layer]/scale;beta=angles[p+layer]
        for i,field in enumerate(h):
            if field:lines.append(f'rz({2*gamma*field:.17g}) q[{i}];')
        for i,j,coupling in couplings:
            lines += [f'cx q[{i}],q[{j}];',f'rz({2*gamma*coupling:.17g}) q[{j}];',f'cx q[{i}],q[{j}];']
        lines += [f'rx({2*beta:.17g}) q[{i}];' for i in range(n)]
    lines += [f'measure q[{i}] -> c[{i}];' for i in range(n)]
    return '\n'.join(lines)+'\n'
