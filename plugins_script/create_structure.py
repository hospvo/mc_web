import os
from datetime import datetime

# Základní cesta k úložišti
#BASE_PATH = r"D:\\minecraft_plugins"
BASE_PATH = r"C:\Users\hospv\Documents\minecraft_plugins"

# Struktura adresářů
DIRECTORY_STRUCTURE = [
    "plugins/core",
    "plugins/optional",
    "plugins/deprecated",
    "configs",
    "backups",
    "temp"
]

# Soubory k vytvoření
FILES_TO_CREATE = [
    "plugins_db.json",
    "update_log.txt"
]

def create_structure():
    try:
        # Vytvoření adresářů
        for directory in DIRECTORY_STRUCTURE:
            path = os.path.join(BASE_PATH, directory)
            os.makedirs(path, exist_ok=True)
            print(f"Created directory: {path}")

        # Vytvoření souborů
        for file in FILES_TO_CREATE:
            path = os.path.join(BASE_PATH, file)
            if not os.path.exists(path):
                with open(path, 'w') as f:
                    if file == "plugins_db.json":
                        f.write('{"plugins": []}')
                    elif file == "update_log.txt":
                        f.write(f"Update log created on {datetime.now()}\n")
                print(f"Created file: {path}")

        print("Directory structure created successfully!")
    except Exception as e:
        print(f"Error creating structure: {str(e)}")

if __name__ == "__main__":
    create_structure()