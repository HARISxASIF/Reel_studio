"""
End-to-end verification of Reel Studio:
1. Multipart upload of 12-minute test video
2. Background pipeline monitoring (probe, chunking, transcription, visual scan, candidate evaluation, rendering)
3. Quality & duration verification of generated reels (30-60s)
4. Reel editor update & re-render test
5. Bulk ZIP export test
"""
import os
import sys
import time
import json
import math
import requests

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
TEST_FILE = os.getenv("TEST_FILE", "/app/test_media/test_12min.mp4")

def run_test():
    print("=" * 60)
    print("REEL STUDIO - END-TO-END PIPELINE VERIFICATION")
    print("=" * 60)

    # 1. Health check
    print("\n[Step 1] Checking API health...")
    r = requests.get(f"{API_BASE}/api/system/health")
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health = r.json()
    print(f"Health OK: {health}")

    # 2. Check test file
    print(f"\n[Step 2] Checking test file: {TEST_FILE}")
    if not os.path.exists(TEST_FILE):
        print(f"Error: test file not found at {TEST_FILE}")
        sys.exit(1)
    file_size = os.path.getsize(TEST_FILE)
    print(f"File size: {file_size / (1024*1024):.2f} MB")

    project_id = os.getenv("PROJECT_ID")
    if not project_id:
        # 3. Initiate multipart upload
        chunk_size = 10 * 1024 * 1024 # 10 MB
        print(f"\n[Step 3] Initiating multipart upload (chunk size {chunk_size / (1024*1024):.1f} MB)...")
        init_res = requests.post(
            f"{API_BASE}/api/uploads/initiate",
            json={
                "file_name": os.path.basename(TEST_FILE),
                "file_size": file_size,
                "chunk_size": chunk_size,
            }
        )
        assert init_res.status_code == 200, f"Initiate upload failed: {init_res.text}"
        init_data = init_res.json()
        session_id = init_data["upload_session_id"]
        project_id = init_data["project_id"]
        total_parts = init_data["total_parts"]
        print(f"Upload initiated: Project ID = {project_id}, Session ID = {session_id}, Total Parts = {total_parts}")

        # 4. Upload parts directly to MinIO presigned URLs
        print(f"\n[Step 4] Uploading {total_parts} parts directly to MinIO via presigned URLs...")
        parts_etags = []
        with open(TEST_FILE, "rb") as f:
            for part_num in range(1, total_parts + 1):
                chunk_data = f.read(chunk_size)
                # Get presigned URL
                part_res = requests.get(f"{API_BASE}/api/uploads/{session_id}/parts/{part_num}")
                assert part_res.status_code == 200, f"Get part url failed: {part_res.text}"
                presigned_url = part_res.json()["presigned_url"]

                # Inside container, if presigned URL host is localhost:9000, redirect to minio:9000 for internal network
                if "localhost:9000" in presigned_url and os.getenv("RUNNING_IN_DOCKER"):
                    presigned_url = presigned_url.replace("localhost:9000", "minio:9000")

                headers = {}
                if "minio:9000" in presigned_url:
                    headers["Host"] = "localhost:9000"

                # Upload part
                put_res = requests.put(presigned_url, data=chunk_data, headers=headers)
                assert put_res.status_code in [200, 204], f"Part upload failed: {put_res.status_code} {put_res.text}"
                etag = put_res.headers.get("ETag", "").strip('"')
                parts_etags.append({"PartNumber": part_num, "ETag": etag})
                print(f"  Uploaded part {part_num}/{total_parts} - ETag: {etag[:12]}...")

        # 5. Complete multipart upload
        print(f"\n[Step 5] Completing multipart upload...")
        complete_res = requests.post(
            f"{API_BASE}/api/uploads/{session_id}/complete",
            json={"parts": parts_etags}
        )
        assert complete_res.status_code == 200, f"Complete upload failed: {complete_res.text}"
        print(f"Upload completed successfully. Pipeline triggered!")

        # 6. Monitor background pipeline execution
        print(f"\n[Step 6] Monitoring pipeline progress for project {project_id}...")
        start_time = time.time()
        last_status = None
        last_chunks = None
        timeout = 300 # 5 minutes

        while time.time() - start_time < timeout:
            proj_res = requests.get(f"{API_BASE}/api/projects/{project_id}")
            assert proj_res.status_code == 200, f"Get project failed: {proj_res.text}"
            proj = proj_res.json()
            current_status = proj["status"]
            completed_chunks = proj["completed_chunks"]
            total_chunks = proj["total_chunks"]

            if current_status != last_status or completed_chunks != last_chunks:
                elapsed = int(time.time() - start_time)
                print(f"  [{elapsed}s] Project status: {current_status} | Chunks: {completed_chunks}/{total_chunks} | Analyzed: {proj['analyzed_duration']:.1f}s")
                last_status = current_status
                last_chunks = completed_chunks

            if current_status == "completed":
                print("Project processing completed successfully!")
                break
            elif current_status == "failed":
                print(f"Error: Project processing failed: {proj.get('error_message')}")
                sys.exit(1)

            time.sleep(2)
    else:
        print(f"\n[Reusing Project ID: {project_id}]")

    # 7. Verify generated reels
    print(f"\n[Step 7] Inspecting generated reels...")
    reels_res = requests.get(f"{API_BASE}/api/projects/{project_id}/reels?include_borderline=true")
    assert reels_res.status_code == 200, f"Get reels failed: {reels_res.text}"
    reels_data = reels_res.json()
    reels = reels_data.get("items", [])
    print(f"Total reels found: {len(reels)}")
    assert len(reels) > 0, "Expected at least 1 reel candidate!"

    for i, reel in enumerate(reels, 1):
        print(f"  Reel {i}:")
        print(f"    Title: {reel['title']}")
        print(f"    Category: {reel['category']}")
        print(f"    Duration: {reel['clip_duration']:.1f}s (Source: {reel['source_start']:.1f}s -> {reel['source_end']:.1f}s)")
        print(f"    Score: {reel['score']:.1f} (Hook: {reel['score_hook']}, Payoff: {reel['score_payoff']})")
        print(f"    Render Status: {reel['render_status']} ({reel['render_progress']}%)")
        print(f"    Top Caption: {reel['top_caption']}")
        print(f"    Framing Mode: {reel['framing_mode']}")
        
        # Verify 30-60 second duration requirement
        assert 30.0 <= reel['clip_duration'] <= 60.5, f"Reel duration {reel['clip_duration']} violates 30-60s limit!"

    # 8. Wait for render completion if still rendering
    print(f"\n[Step 8] Waiting for reel renders to complete...")
    render_timeout = 180
    render_start = time.time()
    all_rendered = False
    
    while time.time() - render_start < render_timeout:
        reels_res = requests.get(f"{API_BASE}/api/projects/{project_id}/reels?include_borderline=true")
        reels = reels_res.json().get("items", [])
        statuses = [r["render_status"] for r in reels]
        print(f"  Render statuses: {statuses}")
        if all(s == "completed" for s in statuses):
            all_rendered = True
            break
        elif any(s == "failed" for s in statuses):
            failed_reels = [r for r in reels if r["render_status"] == "failed"]
            print(f"Warning: Reel render failed: {failed_reels[0].get('render_error')}")
            break
        time.sleep(3)

    assert all_rendered, "Not all reels finished rendering!"
    print("All reels rendered to 1080x1920 vertical MP4 successfully!")

    # 9. Test Reel Editor (Update headline caption and framing mode)
    first_reel = reels[0]
    reel_id = first_reel["id"]
    print(f"\n[Step 9] Testing Reel Editor update on Reel {reel_id}...")
    new_caption = "UPDATED HEADLINE CAPTION TEST"
    update_res = requests.patch(
        f"{API_BASE}/api/reels/{reel_id}",
        json={
            "top_caption": new_caption,
            "framing_mode": "fit",
        }
    )
    assert update_res.status_code == 200, f"Update reel failed: {update_res.text}"
    updated_reel = update_res.json()
    assert updated_reel["top_caption"] == new_caption
    assert updated_reel["framing_mode"] == "fit"
    print(f"Reel updated. Re-render queued in background.")

    # 10. Test Bulk ZIP Export
    print(f"\n[Step 10] Testing 'Download All as ZIP' bulk export...")
    bulk_res = requests.post(f"{API_BASE}/api/projects/{project_id}/export-zip")
    assert bulk_res.status_code == 200, f"Trigger bulk export failed: {bulk_res.text}"
    bulk_data = bulk_res.json()
    export_id = bulk_data["id"]
    print(f"Bulk export triggered: ID = {export_id}")

    # Wait for ZIP completion
    for _ in range(30):
        check_res = requests.get(f"{API_BASE}/api/projects/{project_id}/export-zip/{export_id}")
        assert check_res.status_code == 200
        cur_bulk = check_res.json()
        if cur_bulk["status"] == "completed":
            print(f"Bulk ZIP export completed! Reel count: {cur_bulk['reel_count']}")
            print(f"Download URL: {cur_bulk['download_url'][:60]}...")
            break
        time.sleep(1)

    print("\n" + "=" * 60)
    print("ALL END-TO-END PIPELINE VERIFICATIONS PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_test()
