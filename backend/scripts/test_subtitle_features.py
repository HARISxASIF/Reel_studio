import sys
import time
import requests

API_BASE = "http://localhost:8000"

def run_tests():
    print("=" * 60)
    print("TESTING SUBTITLE FONT RESIZE & ROMAN SCRIPT (ROMAN URDU/HINGLISH)")
    print("=" * 60)

    # 1. Health check
    res = requests.get(f"{API_BASE}/api/system/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("[Step 1] System health OK")

    # 2. Get existing projects to find a reel
    proj_res = requests.get(f"{API_BASE}/api/projects")
    assert proj_res.status_code == 200
    projs = proj_res.json().get("items", [])
    assert len(projs) > 0, "No projects found"
    
    project_id = projs[0]["id"]
    print(f"[Step 2] Testing on Project: {project_id}")

    # 3. Get reels
    reels_res = requests.get(f"{API_BASE}/api/projects/{project_id}/reels?include_borderline=true")
    assert reels_res.status_code == 200
    reels = reels_res.json().get("items", [])
    assert len(reels) > 0, "No reels found"

    test_reel = reels[0]
    reel_id = test_reel["id"]
    print(f"[Step 3] Target Reel: {reel_id}")
    print(f"  Current subtitle_font_size: {test_reel.get('subtitle_font_size')}")

    # 4. Test Subtitle Font Resize
    new_font_size = 76
    print(f"\n[Step 4] Updating subtitle_font_size to {new_font_size}px...")
    patch_res = requests.patch(
        f"{API_BASE}/api/reels/{reel_id}",
        json={"subtitle_font_size": new_font_size}
    )
    assert patch_res.status_code == 200, f"Patch failed: {patch_res.text}"
    updated = patch_res.json()
    assert updated["subtitle_font_size"] == new_font_size, f"Expected {new_font_size}, got {updated.get('subtitle_font_size')}"
    print(f"  Successfully updated subtitle_font_size to: {updated['subtitle_font_size']}px")

    # 5. Test Subtitle Romanization with Urdu & Hindi words
    print(f"\n[Step 5] Testing Roman Urdu & Hinglish conversion...")
    urdu_hindi_words = [
        {"word": "Welcome", "start": 0.0, "end": 0.5},
        {"word": "یہ", "start": 0.5, "end": 1.0},
        {"word": "بہت", "start": 1.0, "end": 1.5},
        {"word": "अच्छा", "start": 1.5, "end": 2.0},
        {"word": "hai", "start": 2.0, "end": 2.5},
    ]

    update_sub_res = requests.patch(
        f"{API_BASE}/api/reels/{reel_id}",
        json={
            "subtitles_json": urdu_hindi_words,
            "subtitle_font_size": 64,
        }
    )
    assert update_sub_res.status_code == 200
    sub_data = update_sub_res.json()
    saved_subtitles = sub_data.get("subtitles_json", [])
    print(f"  Saved subtitles count: {len(saved_subtitles)}")

    from app.services.romanizer import contains_non_latin
    for idx, w in enumerate(saved_subtitles):
        print(f"    Word {idx+1}: '{w['word']}' ({w['start']}s -> {w['end']}s)")
        # Must strictly be in Latin alphabet
        assert not contains_non_latin(w["word"]), f"Word '{w['word']}' still contains non-Latin script!"
        assert w["start"] == urdu_hindi_words[idx]["start"]
        assert w["end"] == urdu_hindi_words[idx]["end"]

    # 6. Test /romanize endpoint directly
    print(f"\n[Step 6] Testing dedicated POST /api/reels/{reel_id}/romanize endpoint...")
    rom_res = requests.post(f"{API_BASE}/api/reels/{reel_id}/romanize")
    assert rom_res.status_code == 200, f"Romanize endpoint failed: {rom_res.text}"
    rom_data = rom_res.json()
    assert rom_data["render_status"] in ["pending", "rendering", "completed"]
    print("  Dedicated romanize endpoint passed!")

    print("\n" + "=" * 60)
    print("ALL SUBTITLE FONT RESIZE & ROMANIZATION TESTS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
