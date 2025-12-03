import requests
import os

def test_process_video():
    url = "http://localhost:8000/process-video"
    video_path = "videos/form.mp4"
    
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return

    print(f"Sending video {video_path} to {url}...")
    
    try:
        with open(video_path, "rb") as f:
            files = {"file": f}
            response = requests.post(url, files=files)
        
        if response.status_code == 200:
            print("Success!")
            print("Response:", response.json())
        else:
            print(f"Failed with status code {response.status_code}")
            print("Response:", response.text)
            
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Is it running?")

if __name__ == "__main__":
    test_process_video()
