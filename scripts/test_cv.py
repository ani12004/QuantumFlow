import _bootstrap
import json
import cv2
from src.vision.detector import Detector

if __name__=='__main__':
    image=cv2.imread(str(_bootstrap.ROOT/'data/raw/cv_test/bus.jpg'))
    result=Detector(_bootstrap.ROOT).detect(image,mode='both')
    if result['counts'].get('person',0)<1 or result['counts'].get('bus',0)<1:raise SystemExit('Reference-image detection failed')
    out=_bootstrap.ROOT/'reports/cv';out.mkdir(exist_ok=True)
    (out/'smoke_test.json').write_text(json.dumps({'test':'Public reference image; not a user camera or accuracy benchmark',**result},indent=2),encoding='utf-8')
    print('Working detector:',result['counts'],'in',round(result['inference_ms']),'ms. No user camera was opened.')
