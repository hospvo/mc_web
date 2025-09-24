import requests

project = "simple-voice-chat"
version = "1.21"
loader = "neoforge"

url = f"https://api.modrinth.com/v2/project/{project}/version"
resp = requests.get(url)
resp.raise_for_status()

for v in resp.json():
    if version in v["game_versions"] and loader in v["loaders"]:
        download_url = v["files"][0]["url"]
        print("Nejnovější build:", v["version_number"])
        print("Download:", download_url)
        break
