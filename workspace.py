import json
from pathlib import Path


DATA_SOURCES_FILE = "data_sources.json"
DEFAULT_FOLDERS = ["data"]


def save_workspaces(folders):
    unique_folders = []

    for folder in folders:
        folder = str(Path(folder).expanduser())

        if folder not in unique_folders:
            unique_folders.append(folder)

    if not unique_folders:
        unique_folders = DEFAULT_FOLDERS

    with open(DATA_SOURCES_FILE, "w", encoding="utf-8") as file:
        json.dump({"folders": unique_folders}, file, indent=2)


def load_workspaces():
    path = Path(DATA_SOURCES_FILE)

    if not path.exists() or path.stat().st_size == 0:
        save_workspaces(DEFAULT_FOLDERS)
        return DEFAULT_FOLDERS

    try:
        with open(path, "r", encoding="utf-8") as file:
            config = json.load(file)

        folders = config.get("folders", DEFAULT_FOLDERS)

        if not folders:
            return DEFAULT_FOLDERS

        return folders

    except json.JSONDecodeError:
        save_workspaces(DEFAULT_FOLDERS)
        return DEFAULT_FOLDERS


def add_workspace(folder):
    if not folder or not folder.strip():
        return False, "Please enter a folder path."

    folder_path = Path(folder).expanduser()

    if not folder_path.exists():
        return False, "Folder does not exist."

    if not folder_path.is_dir():
        return False, "Path is not a folder."

    folders = load_workspaces()
    folder_string = str(folder_path)

    if folder_string not in folders:
        folders.append(folder_string)

    save_workspaces(folders)

    return True, "Workspace added."


def remove_workspace(folder):
    folders = load_workspaces()
    folders = [f for f in folders if f != folder]

    if not folders:
        folders = DEFAULT_FOLDERS

    save_workspaces(folders)

    return True, "Workspace removed."