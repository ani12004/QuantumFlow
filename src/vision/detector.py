import base64,binascii,hashlib,json,threading,time
from pathlib import Path
import numpy as np

COCO=('person bicycle car motorcycle airplane bus train truck boat traffic_light fire_hydrant stop_sign parking_meter bench bird cat dog horse sheep cow elephant bear zebra giraffe backpack umbrella handbag tie suitcase frisbee skis snowboard sports_ball kite baseball_bat baseball_glove skateboard surfboard tennis_racket bottle wine_glass cup fork knife spoon bowl banana apple sandwich orange broccoli carrot hot_dog pizza donut cake chair couch potted_plant bed dining_table toilet tv laptop mouse remote keyboard cell_phone microwave oven toaster sink refrigerator book clock vase scissors teddy_bear hair_drier toothbrush').split()
VEHICLES={1,2,3,5,7}

def letterbox(image,size=640):
    import cv2
    height,width=image.shape[:2];scale=min(size/width,size/height)
    w,h=round(width*scale),round(height*scale);left=(size-w)//2;top=(size-h)//2
    frame=np.full((size,size,3),114,dtype=np.uint8)
    frame[top:top+h,left:left+w]=cv2.resize(image,(w,h))
    tensor=np.ascontiguousarray(frame[:,:,::-1].transpose(2,0,1)[None],dtype=np.float32)/255.
    return tensor,scale,left,top

def postprocess(output,width,height,scale,left,top,threshold,mode):
    rows=np.asarray(output)
    if rows.ndim!=3 or rows.shape[0]!=1 or rows.shape[2]!=6:raise ValueError('Unexpected YOLOv10 output schema')
    result=[]
    for x1,y1,x2,y2,score,cls in rows[0]:
        if not np.isfinite([x1,y1,x2,y2,score,cls]).all() or score<threshold:continue
        label=int(cls)
        if label<0 or label>=len(COCO) or float(label)!=float(cls):continue
        if mode=='person' and label!=0:continue
        if mode=='traffic' and label not in VEHICLES:continue
        if mode=='both' and label not in VEHICLES|{0}:continue
        box=[float(np.clip((x1-left)/scale,0,width)),float(np.clip((y1-top)/scale,0,height)),
             float(np.clip((x2-left)/scale,0,width)),float(np.clip((y2-top)/scale,0,height))]
        if box[2]<=box[0] or box[3]<=box[1]:continue
        result.append({'class_id':label,'label':COCO[label].replace('_',' '),'confidence':float(score),'box':box})
    return result

class Detector:
    def __init__(self,root):
        self.root=Path(root);self.session=None;self.lock=threading.Lock()

    def status(self):
        return {'model':'YOLOv10n · COCO pretrained','ready':(self.root/'models/cv/yolov10n.onnx').is_file(),
                'backend':'ONNX Runtime · local CPU','frames_saved':False,'trained_here':False,
                'limitations':'General object detection, not validated junction tracking, queue estimation or arrival-flow calibration.'}

    def load(self):
        import cv2,onnxruntime as ort
        cv2.setNumThreads(1)
        model=self.root/'models/cv/yolov10n.onnx';manifest=json.loads((model.parent/'manifest.json').read_text(encoding='utf-8'))
        expected=next(a['sha256'] for a in manifest['artifacts'] if a['file_path'].endswith('yolov10n.onnx'))
        if hashlib.sha256(model.read_bytes()).hexdigest()!=expected:raise ValueError('Detector model hash mismatch')
        settings=ort.SessionOptions();settings.intra_op_num_threads=2;settings.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(model),sess_options=settings,providers=['CPUExecutionProvider'])

    def detect(self,image,threshold=.35,mode='person'):
        if mode not in ['person','traffic','both','all']:raise ValueError('Invalid detection mode')
        if type(threshold) not in [int,float] or not np.isfinite(threshold) or not .05<=threshold<=.95:raise ValueError('Confidence must be between 0.05 and 0.95')
        if image is None or image.ndim!=3 or image.shape[2]!=3 or min(image.shape[:2])<16 or max(image.shape[:2])>4096 or image.shape[0]*image.shape[1]>4_000_000:raise ValueError('Image must be 16–4096 pixels per side and at most 4 megapixels')
        if not self.lock.acquire(timeout=5):raise ValueError('Detector is busy; retry in a moment')
        try:
            if self.session is None:self.load()
            start=time.perf_counter();height,width=image.shape[:2];tensor,scale,left,top=letterbox(image)
            output=self.session.run(None,{self.session.get_inputs()[0].name:tensor})[0]
            detections=postprocess(output,width,height,scale,left,top,threshold,mode)
            counts={}
            for d in detections:counts[d['label']]=counts.get(d['label'],0)+1
            return {'width':width,'height':height,'detections':detections,'counts':counts,
                  'inference_ms':(time.perf_counter()-start)*1000,'model':'YOLOv10n COCO pretrained',
                  'observation_type':'Model estimate','units':'detected objects in this frame; not unique arrivals',
                  'frames_saved':False,'camera_calibrated':False}
        finally:self.lock.release()

    def from_payload(self,payload):
        import cv2
        value=payload.get('image')
        if not isinstance(value,str) or len(value)>1_800_000:raise ValueError('Image must be a JPEG/PNG data URL under 1.8 MB')
        if not value.startswith(('data:image/jpeg;base64,','data:image/png;base64,')):raise ValueError('JPEG or PNG data URL required')
        try:data=base64.b64decode(value.split(',',1)[1],validate=True)
        except (ValueError,binascii.Error):raise ValueError('Invalid encoded image')
        image=cv2.imdecode(np.frombuffer(data,dtype=np.uint8),cv2.IMREAD_COLOR)
        return self.detect(image,payload.get('confidence',.35),payload.get('mode','person'))
