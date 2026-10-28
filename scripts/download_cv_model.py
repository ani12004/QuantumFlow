"""Download a pinned public ONNX model, record provenance, and retain its license card."""
import _bootstrap
import hashlib,json,ssl,urllib.request
from datetime import datetime,timezone
import certifi
ROOT=_bootstrap.ROOT
REPO='onnx-community/YOLOv10'
REVISION='c03e02456387191807059ef0ebe2c56315ddff55'

def download(url,path,max_bytes):
    req=urllib.request.Request(url,headers={'User-Agent':'QuantumFlow-BLR research/1.0'})
    context=ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(req,context=context,timeout=90) as response:
        data=response.read(max_bytes+1)
    if len(data)>max_bytes:raise ValueError('Download too large')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=data:raise ValueError('Refusing to replace a different artifact: '+str(path))
    path.write_bytes(data)
    return {'url':url,'file_path':path.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'downloaded_at':datetime.now(timezone.utc).isoformat()}

def main():
    dest=ROOT/'models/cv';dest.mkdir(parents=True,exist_ok=True)
    artifacts=[]
    for name in ['yolov10n.onnx','README.md']:
        artifacts.append(download(f'https://huggingface.co/{REPO}/resolve/{REVISION}/{name}',dest/name,40_000_000))
    # Public, non-user image for functional smoke tests. Never use a user's camera to test automatically.
    artifacts.append(download('https://raw.githubusercontent.com/ultralytics/assets/main/im/bus.jpg',ROOT/'data/raw/cv_test/bus.jpg',3_000_000))
    manifest={'name':'YOLOv10n COCO, ONNX export','original_model_publisher':'THU-MIG / YOLOv10 authors; COCO pretrained',
       'export_publisher':'onnx-community','repository':'https://huggingface.co/'+REPO,'revision':REVISION,
       'license':'AGPL-3.0 (model repository); original model and export rights apply',
       'original_source':'https://github.com/THU-MIG/yolov10',
       'training_status':'Pretrained externally; not trained or fine-tuned on user images or Bengaluru CCTV here',
       'test_image':'Public Ultralytics bus image, used only for a functional test; original image rights not independently resolved. Not camera data.',
       'artifacts':artifacts}
    (dest/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Downloaded CPU detector and public test image; provenance saved in models/cv/manifest.json')

if __name__=='__main__':main()
