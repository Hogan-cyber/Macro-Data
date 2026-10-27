"""R and Python must produce the same weekly inputs, splits and numeric features."""
from pathlib import Path
import pandas as pd
root=Path(__file__).resolve().parents[1]/'ml/output'
for name in ['weekly_inputs','features_before_split','train','validation','test']:
    a=pd.read_csv(root/'python'/f'{name}.csv').sort_index(axis=1)
    b=pd.read_csv(root/'R'/f'{name}.csv').sort_index(axis=1)
    pd.testing.assert_frame_equal(a,b,check_dtype=False,atol=1e-9,rtol=1e-9)
print('Python and R outputs match: weekly inputs, features, train/validation/test.')
