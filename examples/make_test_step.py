from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer
from OCC.Core.IFSelect import IFSelect_RetDone

shape = BRepPrimAPI_MakeBox(50.0, 30.0, 10.0).Shape()
out = "/Users/eoincobbe/dev/cnc-dfm/examples/test_box.step"
writer = STEPControl_Writer()
writer.Transfer(shape, STEPControl_AsIs)
status = writer.Write(out)
if status != IFSelect_RetDone:
    raise SystemExit(f"STEP write failed: {status}")
print(out)
