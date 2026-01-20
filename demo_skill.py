import sys
import os

# Ensure we can import the package
sys.path.append(os.getcwd())

try:
    from skillware.skills.examples.helicopter_pilot import HelicopterPilotSkill
    
    print("[SUCCESS] Successfully imported HelicopterPilotSkill")
    
    skill = HelicopterPilotSkill()
    print(f"[INFO] Loaded Skill: {skill.manifest['name']} v{skill.manifest['version']}")
    
    params = {"destination": "Matrix Mainframe", "flight_mode": "urgent"}
    result = skill.execute(params)
    
    print(f"[SUCCESS] Execution Result: {result}")

except ImportError as e:
    print(f"[ERROR] ImportError: {e}")
except Exception as e:
    print(f"[ERROR] Error: {e}")
