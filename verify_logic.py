
import sys
import os
import shutil
import json
from pathlib import Path

# Add project root to path
sys.path.append("d:/projects/ags")

# Mocking config to avoid import errors if config.py needs env vars
# Assuming helpers don't need app context
from tbag.helpers.components import save_component, load_component, new_component_slug, COMPONENTS
from tbag.helpers.projects import save_config, load_config, new_project_slug, PROJECTS

def test_logic():
    print("Testing Thickness Logic...")
    
    # --- Component Test ---
    c_name = "ThickTestComp"
    cid = new_component_slug(c_name)
    print(f"1. Creating component '{c_name}' (ID: {cid}) with default_thickness=0.55")
    
    c_data = {
        "name": c_name,
        "gpio": 2, # L1
        "image": None,
        "default_thickness": 0.55
    }
    
    save_component(cid, c_data)
    
    # Reload and verify
    loaded_c = load_component(cid)
    if loaded_c and loaded_c.get("default_thickness") == 0.55:
        print("   [PASS] Component saved and loaded with default_thickness.")
    else:
        print(f"   [FAIL] Component data mismatch: {loaded_c}")

    # --- Project Test ---
    p_name = "ThickTestProj"
    pid = new_project_slug(p_name)
    print(f"2. Creating project '{p_name}' (ID: {pid}) with sequence thickness override.")
    
    p_data = {
        "name": p_name,
        "sequence": [
            {"comp": cid, "label": "Step 1", "thickness": 1.25},
            {"comp": cid, "label": "Step 2"} # Should imply default or 0 (logic handles missing key)
        ]
    }
    
    save_config(pid, p_data)
    
    # Reload and verify
    loaded_p = load_config(pid)
    seq = loaded_p.get("sequence", [])
    
    if len(seq) == 2:
        if seq[0].get("thickness") == 1.25:
             print("   [PASS] Step 1 has thickness 1.25")
        else:
             print(f"   [FAIL] Step 1 thickness mismatch: {seq[0]}")
             
        if "thickness" not in seq[1]:
             print("   [PASS] Step 2 has no explicit thickness (correct).")
        else:
             print(f"   [INFO] Step 2 has thickness: {seq[1].get('thickness')}")
    else:
        print("   [FAIL] Sequence length mismatch.")

    # Cleanup
    print("Cleaning up...")
    shutil.rmtree(COMPONENTS / cid, ignore_errors=True)
    shutil.rmtree(PROJECTS / pid, ignore_errors=True)
    print("Done.")

if __name__ == "__main__":
    test_logic()
