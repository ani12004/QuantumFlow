"""Export actual recorded signals into standalone SUMO configurations."""
import os,json,subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
import pandas as pd
from src.simulation.scenario import xml_write,executable
from src.simulation.runner import signal_states

def create_replays(directory):
    manifest=json.loads((directory/'experiment_manifest.json').read_text(encoding='utf-8'));c=manifest['config'];net=directory/'scenario/junction.net.xml'
    states=signal_states(net);configs=[]
    for seed in c['seeds']:
        route=directory/'scenario'/f'demand_seed_{seed}.rou.xml'
        for controller in ['fixed_time','classical_exact','qaoa']:
            target=directory/f'seed_{seed}'/controller;trace=pd.read_csv(target/'traffic_state.csv')
            root=ET.Element('additional');logic=ET.SubElement(root,'tlLogic',id='J0',type='static',programID='replay',offset='0')
            groups=trace.phase.ne(trace.phase.shift()).cumsum()
            for _,rows in trace.groupby(groups):ET.SubElement(logic,'phase',duration=str(len(rows)),state=states[rows.phase.iloc[0]])
            xml_write(target/'replay_signals.add.xml',root)
            config=ET.Element('configuration');input_=ET.SubElement(config,'input')
            relative=lambda p:os.path.relpath(p,target).replace('\\','/')
            ET.SubElement(input_,'net-file',value=relative(net));ET.SubElement(input_,'route-files',value=relative(route))
            ET.SubElement(input_,'additional-files',value='replay_signals.add.xml')
            timing=ET.SubElement(config,'time');ET.SubElement(timing,'begin',value='0');ET.SubElement(timing,'end',value=str(len(trace)));ET.SubElement(timing,'step-length',value='1')
            random=ET.SubElement(config,'random_number');ET.SubElement(random,'seed',value=str(seed))
            process=ET.SubElement(config,'processing');ET.SubElement(process,'time-to-teleport',value='-1');ET.SubElement(process,'collision.action',value='warn')
            path=target/'replay.sumocfg';xml_write(path,config);configs.append(path)
    return configs

def validate_replay(root,config):
    target=config.parent/'replay_validation_tripinfo.xml'
    subprocess.run([executable('sumo',root),'-c',str(config),'--tripinfo-output',str(target),'--tripinfo-output.write-unfinished','true','--no-step-log','true','--duration-log.disable','true'],check=True,capture_output=True,text=True)
    reference={r.get('id'):r.attrib for r in ET.parse(config.parent/'tripinfo.xml').getroot().findall('tripinfo')}
    actual={r.get('id'):r.attrib for r in ET.parse(target).getroot().findall('tripinfo')}
    if set(reference)!=set(actual):raise AssertionError('Replay vehicle IDs differ')
    max_error=0.
    for vehicle in reference:
        for field in ['arrival','waitingTime','timeLoss','departDelay']:
            max_error=max(max_error,abs(float(reference[vehicle][field])-float(actual[vehicle][field])))
    if max_error>.001:raise AssertionError(f'Replay diverged from TraCI output by {max_error}s')
    result={'replay_config':str(config),'vehicles':len(actual),'max_trip_metric_difference_seconds':max_error,'validated':True}
    (config.parent/'replay_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
