import asyncio
import os
import time
from pathlib import Path

import httpx

API_URL = "http://localhost:8000/api/documents/upload"
STATUS_URL = "http://localhost:8000/api/documents"
SAMPLE_DIR = Path("d:/superjoin/data/sample")

async def upload_pdf(client: httpx.AsyncClient, file_path: Path):
    print(f"Uploading {file_path.name}...")
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        response = await client.post(API_URL, files=files, timeout=60.0)
        
    if response.status_code == 200:
        data = response.json()
        print(f"[SUCCESS] {file_path.name}: {data['status']} - {data['message']}")
        return data
    else:
        print(f"[FAILED] {file_path.name} Failed: {response.text}")
        return None

async def wait_for_processing(client: httpx.AsyncClient):
    print("\nWaiting for processing to complete...")
    while True:
        response = await client.get(STATUS_URL)
        if response.status_code != 200:
            print("Failed to get status")
            break
            
        data = response.json()
        documents = data.get("documents", [])
        
        processing = [d for d in documents if d["status"] in ["processing", "starting"]]
        completed = [d for d in documents if d["status"] == "completed"]
        failed = [d for d in documents if d["status"] == "failed"]
        
        print(f"\rStatus: {len(processing)} processing, {len(completed)} completed, {len(failed)} failed", end="")
        
        if len(processing) == 0:
            print("\n\nProcessing finished!")
            for doc in documents:
                print(f"- {doc['filename']}: {doc['status']} (Claims: {doc.get('metadata', {}).get('total_claims', 0)})")
            break
            
        await asyncio.sleep(5)

async def main():
    if not SAMPLE_DIR.exists():
        print(f"Sample directory {SAMPLE_DIR} not found.")
        return

    pdf_files = list(SAMPLE_DIR.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in sample directory.")
        return

    print(f"Found {len(pdf_files)} PDF files to process.")
    
    async with httpx.AsyncClient() as client:
        for pdf_file in pdf_files:
            print(f"\n==========================================")
            print(f"Uploading and processing: {pdf_file.name}")
            print(f"==========================================")
            await upload_pdf(client, pdf_file)
            # Wait for this document to finish processing before uploading the next
            await wait_for_processing(client)
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
