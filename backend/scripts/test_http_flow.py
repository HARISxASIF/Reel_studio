import requests
import json

import os

BASE = os.getenv("API_URL", "http://api:8000/api")

def test_api_workflow():
    print("Testing HTTP API Workflow...")
    # 1. Create a project via upload initiate
    res = requests.post(
        "http://api:8000/api/uploads/initiate",
        json={"file_name": "test_12min.mp4", "file_size": 63848750}
    )
    assert res.status_code == 200, res.text
    init_res = res.json()
    pid = init_res["project_id"]
    print(f"1. Project created via upload initiate: {pid}")

    # 2. Update settings via PATCH
    patch_payload = {
        "framing_mode": "split",
        "split_facecam_crop": {"x": 0.6, "y": 0.05, "width": 0.35, "height": 0.35},
        "split_gameplay_crop": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "split_order": "facecam_top",
        "split_ratio": 0.35,
        "subtitle_font_size": 66
    }
    res = requests.patch(f"{BASE}/projects/{pid}/settings", json=patch_payload)
    assert res.status_code == 200, res.text
    updated = res.json()
    print(f"2. Settings saved: framing={updated['framing_mode']}, subtitle_size={updated['subtitle_font_size']}")
    assert updated["framing_mode"] == "split"
    assert updated["subtitle_font_size"] == 66
    assert updated["split_facecam_crop"]["x"] == 0.6

    # 3. Test reject invalid split on generate
    invalid_gen = {
        "framing_mode": "split",
        "split_facecam_crop": {"x": 0.8, "y": 0.1, "width": 0.4, "height": 0.4}
    }
    res = requests.post(f"{BASE}/projects/{pid}/generate", json=invalid_gen)
    assert res.status_code == 400, f"Expected 400, got {res.status_code}"
    print(f"3. Invalid split generation properly rejected: {res.json()['detail']}")

    # 4. Test generate when source media key not yet set
    res = requests.post(f"{BASE}/projects/{pid}/generate")
    assert res.status_code == 400
    print(f"4. Generation without ready source properly rejected: {res.json()['detail']}")

    # 5. Now update project directly in DB to have ready source media
    import asyncio
    from app.database import AsyncSessionLocal
    from app.models.project import Project
    from sqlalchemy import select
    import uuid

    async def make_ready():
        async with AsyncSessionLocal() as session:
            q = await session.execute(select(Project).where(Project.id == uuid.UUID(pid)))
            p = q.scalar_one()
            p.source_file_key = "test_media/test_12min.mp4"
            p.duration = 720.0
            p.status = "ready"
            await session.commit()
    asyncio.run(make_ready())

    # 6. Verify HTTP rejection of out-of-bounds split crop on ready project
    res = requests.post(f"{BASE}/projects/{pid}/generate", json=invalid_gen)
    assert res.status_code == 400
    print(f"5. Generation with out-of-bounds crop rejected: {res.json()['detail']}")

    # 7. Verify successful generation with valid split settings
    valid_gen = {
        "framing_mode": "split",
        "split_facecam_crop": {"x": 0.6, "y": 0.05, "width": 0.35, "height": 0.35},
        "split_gameplay_crop": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
        "split_order": "facecam_top",
        "split_ratio": 0.35,
        "subtitle_font_size": 66
    }
    res = requests.post(f"{BASE}/projects/{pid}/generate", json=valid_gen)
    assert res.status_code == 200, res.text
    gen_proj = res.json()
    assert gen_proj["status"] == "analyzing"
    assert gen_proj["settings_snapshot"] is not None
    assert gen_proj["settings_snapshot"]["framing_mode"] == "split"
    assert gen_proj["settings_snapshot"]["subtitle_font_size"] == 66
    print(f"6. Generation started successfully! Snapshot captured: {gen_proj['settings_snapshot']['framing_mode']}, font={gen_proj['settings_snapshot']['subtitle_font_size']}")

    print("ALL HTTP API CHECKS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_api_workflow()
