import numpy as np
from carbon_mrv.data.gfc import decode_lossyear,loss_mask_for_transition
from carbon_mrv.data.modis import qa_bits,valid_burn_mask
from carbon_mrv.quality.scl import scl_valid_mask

def test_scl_mask_policy():
    scl=np.arange(12,dtype=np.uint8); valid=scl_valid_mask(scl)
    for code in [0,1,2,3,6,8,9,10,11]: assert not valid[code]
    assert valid[4] and valid[5] and valid[7]; assert not scl_valid_mask(scl,allow_low_confidence=False)[7]

def test_gfc_year_decode():
    arr=decode_lossyear(np.array([0,19,20,24],dtype=np.uint8)); assert arr.tolist()==[0,2019,2020,2024]
    assert loss_mask_for_transition(np.array([20]),2019,2020)[0]

def test_modis_qa_requires_land_and_valid_data():
    qa=np.array([0,1,2,3],dtype=np.uint8); mask=valid_burn_mask(np.array([100,100,100,100]),qa)
    assert mask.tolist()==[False,False,False,True]
    bits=qa_bits(qa); assert bits["land"].tolist()==[False,True,False,True]
