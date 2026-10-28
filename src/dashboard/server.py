import json,mimetypes,os,secrets,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs
import numpy as np
from src.dashboard.data import clean,read_json,overview,dataset,experiment_path,run_check,frame,artifact_paths,CONTROLLERS

class Dashboard:
    def __init__(self,root):
        self.root=root;self.jobs={};self.executor=ThreadPoolExecutor(max_workers=1);self.lock=threading.Lock()
        from src.vision.detector import Detector
        self.detector=Detector(root)

    def submit(self,kind,payload):
        with self.lock:
            if any(j['status'] in ['queued','running'] for j in self.jobs.values()):raise ValueError('An experiment or solve is already running. Wait for it to finish.')
            job_id=uuid.uuid4().hex[:16];job={'id':job_id,'kind':kind,'status':'queued','created_at':time.time()};self.jobs[job_id]=job
        def work():
            job['status']='running'
            try:
                job['result']=clean(self.solve(payload) if kind=='solve' else self.experiment(payload,job_id));job['status']='completed'
            except Exception as e:job['status']='failed';job['error']=str(e)
        self.executor.submit(work)
        return job.copy()

    def solve(self,payload):
        from src.optimization.qubo import build_qubo,solve_exact
        from src.optimization.qaoa import solve_qaoa,statevector,qasm
        c=read_json(self.root/'configs/simulation_demo.json');queues=payload.get('queues');rates=payload.get('rates')
        for values,upper in [(queues,200),(rates,3000)]:
            if not isinstance(values,list) or len(values)!=4 or any(type(v) not in [float,int] or not np.isfinite(v) or v<0 or v>upper for v in values):raise ValueError('Enter four valid nonnegative queue/rate values within the displayed limits')
        layers=payload.get('layers',2);shots=payload.get('shots',256)
        if type(layers)!=int or layers not in [1,2,3] or type(shots)!=int or shots not in [128,256,512,1024]:raise ValueError('Unsupported layer/shot setting')
        c['qaoa']['layers']=layers;c['qaoa']['shots']=shots
        qubo=build_qubo(queues,np.array(rates)/3600,c);q=solve_qaoa(qubo,c['qaoa'],42);reference=solve_exact(qubo)
        bits,energies=qubo.all_energies();psi=statevector(energies,qubo.n,q['parameters'],q['energy_scale']);probs=abs(psi)**2
        indices=[i for i in range(len(bits)) if qubo.feasible(bits[i])];indices.sort(key=lambda i:-probs[i])
        distribution=[{'greens':qubo.decode(bits[i]),'probability':float(probs[i]),'energy':float(energies[i])} for i in indices]
        return {'source_id':'dashboard_user_simulated_state','observation_type':'Simulation','queues':queues,'rates':rates,
                'qaoa':q,'classical':reference,'gap':max(0.,q['energy']-reference['energy']),
                'matrix':qubo.matrix.tolist(),'qubo_offset':qubo.offset,'constraint_penalty':qubo.penalty,
                'variable_order':[f'cycle_{cycle}_ns_{green}' for cycle in range(2) for green in qubo.options],
                'circuit_qasm':qasm(qubo,q),'feasible_costs':qubo.feasible_costs.tolist(),'distribution':distribution,
                'note':'Noiseless quantum circuit simulated on a classical CPU. This changes neither the reference experiment nor a real signal.'}

    def experiment(self,payload,job_id):
        from src.simulation.runner import run_experiment
        from src.simulation.replay import create_replays
        seeds=payload.get('seeds',[11])
        if not isinstance(seeds,list) or not 1<=len(seeds)<=3 or len(set(seeds))!=len(seeds) or any(type(s)!=int or s<1 or s>9999 for s in seeds):raise ValueError('Choose one to three integer seeds in [1,9999]')
        c=read_json(self.root/'configs/simulation_demo.json');c['seeds']=seeds
        directory=self.root/'reports/dashboard_runs'/('exp_'+job_id);results=run_experiment(self.root,c,directory);create_replays(directory)
        # Import the existing report entrypoint without changing original reference artifacts.
        from scripts.report_quantum_demo import generate_report
        generate_report(directory,save_reference=False)
        return {'run':'exp_'+job_id,'results':results,'report':(directory/'simulation_report.md').relative_to(self.root).as_posix()}

    def handler(self):
        app=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,fmt,*args):pass
            def headers_common(self):
                self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
                self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            def respond(self,data,status=200):
                blob=json.dumps(clean(data),allow_nan=False).encode('utf-8');self.send_response(status);self.headers_common()
                self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(blob)));self.end_headers();self.wfile.write(blob)
            def local_host(self):
                return self.headers.get('Host') in [f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']
            def do_GET(self):
                if not self.local_host():return self.respond({'error':'Local host required'},403)
                try:
                    url=urlparse(self.path);query=parse_qs(url.query);get=lambda k,d=None:query.get(k,[d])[0];run=get('run','reference')
                    if url.path=='/api/cv/status':return self.respond(app.detector.status())
                    if url.path=='/api/overview':return self.respond(overview(app.root,run))
                    if url.path in ['/api/replay','/api/decisions','/api/qubo']:
                        path=run_check(app.root,run,int(get('seed','11')),get('controller','qaoa'))
                        if url.path=='/api/replay':return self.respond(frame(path/'traffic_state.csv').fillna('').to_dict('records'))
                        return self.respond(read_json(path/('decisions.json' if url.path=='/api/decisions' else 'first_qubo.json'),[]))
                    if url.path=='/api/dataset':
                        offset=int(get('offset','0'));limit=int(get('limit','50'))
                        if offset<0 or not 1<=limit<=250:raise ValueError('Invalid page')
                        return self.respond(dataset(app.root,get('name','demand'),offset,limit,get('q','')))
                    if url.path=='/api/artifacts':return self.respond([{'file':k,'bytes':v.stat().st_size} for k,v in sorted(artifact_paths(app.root).items())])
                    if url.path.startswith('/api/jobs/'):
                        job=app.jobs.get(url.path.split('/')[-1]);return self.respond(job if job else {'error':'Unknown job'},200 if job else 404)
                    if url.path=='/api/download':
                        path=artifact_paths(app.root).get(get('file'))
                        if path is None:raise ValueError('Unknown artifact')
                        blob=path.read_bytes();self.send_response(200);self.headers_common();self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
                        self.send_header('Content-Disposition','attachment; filename="'+path.name+'"');self.send_header('Content-Length',str(len(blob)));self.end_headers();return self.wfile.write(blob)
                    static={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css','/favicon.svg':'favicon.svg','/camera':'camera.html','/camera.js':'camera.js','/camera.css':'camera.css'}
                    if url.path in static:
                        path=app.root/'dashboard'/static[url.path];blob=path.read_bytes();self.send_response(200);self.headers_common()
                        self.send_header('Content-Type',mimetypes.guess_type(path.name)[0] or 'text/plain');self.send_header('Content-Length',str(len(blob)));self.end_headers();return self.wfile.write(blob)
                    return self.respond({'error':'Not found'},404)
                except (ValueError,KeyError,FileNotFoundError) as e:return self.respond({'error':str(e)},400)
                except Exception as e:return self.respond({'error':str(e)},500)
            def do_POST(self):
                if not self.local_host():return self.respond({'error':'Local host required'},403)
                origin=self.headers.get('Origin')
                if origin and origin not in [f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}']:return self.respond({'error':'Same-origin request required'},403)
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':return self.respond({'error':'JSON body required'},415)
                try:
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=(2_000_000 if self.path=='/api/cv/detect' else 16384):raise ValueError('Invalid request size')
                    payload=json.loads(self.rfile.read(size))
                    if not isinstance(payload,dict):raise ValueError('JSON object required')
                    if self.path=='/api/cv/detect':return self.respond(app.detector.from_payload(payload))
                    if self.path not in ['/api/solve','/api/experiments']:return self.respond({'error':'Not found'},404)
                    return self.respond(app.submit('solve' if self.path=='/api/solve' else 'experiment',payload),202)
                except (ValueError,KeyError) as e:return self.respond({'error':str(e)},400)
        return Handler

def serve(root,port=8765):
    app=Dashboard(root);server=ThreadingHTTPServer(('127.0.0.1',port),app.handler())
    print(f'QuantumFlow dashboard: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();app.executor.shutdown(wait=False,cancel_futures=True)
