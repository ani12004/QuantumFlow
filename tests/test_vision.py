import base64,json
from pathlib import Path
import numpy as np
import pytest
from src.vision.detector import Detector,letterbox,postprocess
ROOT=Path(__file__).resolve().parents[1]

def test_letterbox_geometry_and_rgb():
    image=np.zeros((320,640,3),dtype=np.uint8);image[:,:,2]=255
    tensor,scale,left,top=letterbox(image)
    assert tensor.shape==(1,3,640,640) and scale==1 and top==160 and left==0
    assert tensor[0,0,200,100]==1 and tensor[0,2,200,100]==0

def test_model_boxes_unpad_and_filter_classes():
    output=np.array([[[10,170,110,270,.9,0],[20,180,120,280,.8,5],[1,2,3,4,.1,0]]])
    person=postprocess(output,640,320,1,0,160,.35,'person')
    assert len(person)==1 and person[0]['box']==[10,10,110,110]
    assert postprocess(output,640,320,1,0,160,.35,'traffic')[0]['label']=='bus'
    assert len(postprocess(output,640,320,1,0,160,.35,'both'))==2

def test_invalid_camera_payload_rejected():
    detector=Detector(ROOT)
    for payload in [{},{'image':'https://example.com/photo.jpg'},{'image':'data:image/jpeg;base64,notbase64!'}]:
        with pytest.raises(ValueError):detector.from_payload(payload)
    with pytest.raises(ValueError):detector.detect(np.zeros((20,20,3),dtype=np.uint8),threshold=float('nan'))
    with pytest.raises(ValueError):detector.detect(None)

def test_pretrained_detector_on_public_image_not_user_camera():
    import cv2
    detector=Detector(ROOT);image=cv2.imread(str(ROOT/'data/raw/cv_test/bus.jpg'))
    result=detector.detect(image,mode='both')
    assert result['counts'].get('person',0)>=1 and result['counts'].get('bus',0)>=1
    assert result['observation_type']=='Model estimate' and result['frames_saved'] is False
    assert all(0<=d['box'][0]<d['box'][2]<=result['width'] for d in result['detections'])
    assert all(0<=d['box'][1]<d['box'][3]<=result['height'] for d in result['detections'])
    people=detector.detect(image,mode='person')
    assert all(d['label']=='person' for d in people['detections'])
