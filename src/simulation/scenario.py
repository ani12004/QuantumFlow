import json,os,shutil,subprocess,sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from src.ingestion import sha256
from src.optimization.qubo import APPROACHES,phase_schedule

def executable(name,root):
    suffix='.exe' if os.name=='nt' else ''
    candidates=[root/'.deps/sumo/bin'/(name+suffix)]
    if os.environ.get('SUMO_HOME'):candidates.append(Path(os.environ['SUMO_HOME'])/'bin'/(name+suffix))
    installed=shutil.which(name)
    if installed:candidates.append(Path(installed))
    # pip-installed package in a virtualenv without a project .deps directory.
    try:
        import sumo
        candidates.append(Path(sumo.__file__).parent/'bin'/(name+suffix))
    except ImportError:pass
    for p in candidates:
        if p.is_file():return str(p.resolve())
    raise FileNotFoundError(f'{name} not found; install requirements-simulation.txt or configure SUMO_HOME')

def xml_write(path,element):
    ET.indent(element);ET.ElementTree(element).write(path,encoding='utf-8',xml_declaration=True)

def validate_config(c):
    if c.get('observation_type')!='Simulation':raise ValueError('Explicit Simulation label required')
    ints=['cycle_seconds','yellow_seconds','all_red_seconds','demand_seconds','drain_seconds','warmup_seconds','arrival_estimator_window_seconds']
    if any(not isinstance(c.get(k),int) or c[k]<=0 for k in ints):raise ValueError('Positive integer timing values required')
    if c['warmup_seconds']>=c['demand_seconds']:raise ValueError('Warmup must end before demand')
    if c['warmup_seconds']%c['cycle_seconds']:raise ValueError('Warmup must end on cycle boundary')
    if c['planning_cycles']!=2:raise ValueError('Two-cycle planning required')
    if len(c['green_options_ns_seconds'])>8 or len(set(c['green_options_ns_seconds']))!=len(c['green_options_ns_seconds']):raise ValueError('Unique options, <=16 qubits required')
    if c['fixed_green_ns_seconds'] not in c['green_options_ns_seconds']:raise ValueError('Fixed green must be an option')
    for g in c['green_options_ns_seconds']:
        if not isinstance(g,int):raise ValueError('Integer greens required')
        phase_schedule(g,c)
    for key in ['saturation_flow_veh_per_second_per_lane','terminal_queue_weight_seconds_per_vehicle','split_change_weight_vehicle_seconds_per_second_squared','arm_length_m','speed_m_per_s']:
        if not np.isfinite(c[key]) or c[key]<0:raise ValueError('Invalid '+key)
    if c['saturation_flow_veh_per_second_per_lane']<=0:raise ValueError('Positive saturation flow required')
    cursor=0
    for profile in c['demand_profiles']:
        if profile['begin_seconds']!=cursor or profile['end_seconds']<=cursor:raise ValueError('Profiles must be contiguous')
        if any(not np.isfinite(profile[a]) or profile[a]<0 for a in APPROACHES):raise ValueError('Invalid demand rate')
        cursor=profile['end_seconds']
    if cursor!=c['demand_seconds']:raise ValueError('Profiles must cover demand horizon exactly')
    if not c['seeds'] or len(set(c['seeds']))!=len(c['seeds']):raise ValueError('Unique nonempty seeds required')
    for k in ['layers','shots','restarts','max_iterations']:
        if not isinstance(c['qaoa'][k],int) or c['qaoa'][k]<1:raise ValueError('Invalid QAOA '+k)

def build_network(root,c,directory):
    directory.mkdir(parents=True,exist_ok=True);length=c['arm_length_m']
    nodes=ET.Element('nodes');ET.SubElement(nodes,'node',id='J0',x='0',y='0',type='traffic_light')
    for a,(x,y) in {'N':(0,length),'S':(0,-length),'E':(length,0),'W':(-length,0)}.items():
        ET.SubElement(nodes,'node',id=a,x=str(x),y=str(y),type='priority')
    edges=ET.Element('edges')
    for a in APPROACHES:
        ET.SubElement(edges,'edge',{'id':a+'_in','from':a,'to':'J0','numLanes':'1','speed':str(c['speed_m_per_s'])})
        ET.SubElement(edges,'edge',{'id':a+'_out','from':'J0','to':a,'numLanes':'1','speed':str(c['speed_m_per_s'])})
    con=ET.Element('connections')
    for index,(a,b) in enumerate([('N','S'),('S','N'),('E','W'),('W','E')]):
        ET.SubElement(con,'connection',{'from':a+'_in','to':b+'_out','fromLane':'0','toLane':'0','tl':'J0','linkIndex':str(index)})
    for name,elem in [('junction.nod.xml',nodes),('junction.edg.xml',edges),('junction.con.xml',con)]:xml_write(directory/name,elem)
    net=directory/'junction.net.xml'
    command=[executable('netconvert',root),'--node-files',str(directory/'junction.nod.xml'),'--edge-files',str(directory/'junction.edg.xml'),
             '--connection-files',str(directory/'junction.con.xml'),'--output-file',str(net),'--no-turnarounds','true','--lefthand','true',
             '--no-warnings','true']
    p=subprocess.run(command,capture_output=True,text=True,check=True)
    (directory/'netconvert.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    parsed=ET.parse(net).getroot();mapping=[]
    for e in parsed.findall('connection'):
        if e.get('tl')=='J0':mapping.append((e.get('from'),e.get('to'),int(e.get('linkIndex'))))
    expected=[(a+'_in',b+'_out',i) for i,(a,b) in enumerate([('N','S'),('S','N'),('E','W'),('W','E')])]
    # netconvert may reorder TLS indices. Verify movements, then derive states from output indices.
    if sorted((a,b) for a,b,_ in mapping)!=sorted((a,b) for a,b,_ in expected) or sorted(i for _,_,i in mapping)!=list(range(4)):
        raise ValueError('Unexpected SUMO TLS movements; do not run unverified states')
    (directory/'verified_link_mapping.json').write_text(json.dumps(mapping,indent=2))
    return net

def make_demand(c,seed,path):
    """Piecewise Poisson entry attempts, sampled once and shared by all controllers."""
    rng=np.random.default_rng(seed);vehicles=[]
    for p in c['demand_profiles']:
        for a in APPROACHES:
            rate=p[a]/3600
            if not rate:continue
            time=p['begin_seconds']+rng.exponential(1/rate)
            while time<p['end_seconds']:
                vehicles.append({'approach':a,'depart':float(time)});time+=rng.exponential(1/rate)
    vehicles.sort(key=lambda v:(v['depart'],v['approach']))
    tree=ET.Element('routes');ET.SubElement(tree,'vType',id='car',vClass='passenger',accel='2.6',decel='4.5',sigma='0.5',tau='1.0',length='5',minGap='2.5')
    for a,b in [('N','S'),('S','N'),('E','W'),('W','E')]:ET.SubElement(tree,'route',id='r_'+a,edges=a+'_in '+b+'_out')
    for i,v in enumerate(vehicles):
        v['vehicle_id']=f'{v["approach"]}_{i}'
        ET.SubElement(tree,'vehicle',id=v['vehicle_id'],type='car',route='r_'+v['approach'],depart=f'{v["depart"]:.3f}',departLane='0',departSpeed='max')
        v['depart']=round(v['depart'],3)
    xml_write(path,tree)
    return vehicles
