import os
from git import Repo
from collections import OrderedDict

REPO_URL = "https://github.com/AbhigyanVE/ScrumMaster"
LOCAL_REPO_DIR = "./ScrumMaster"
OUTPUT_FILE = "RELEASE_NOTES.md"


def clone_or_open_repo():
    if os.path.exists(LOCAL_REPO_DIR):
        print("📂 Using existing local repository")
        return Repo(LOCAL_REPO_DIR)
    else:
        print("⬇️ Cloning repository...")
        return Repo.clone_from(REPO_URL, LOCAL_REPO_DIR)


def extract_release_notes(repo):
    releases = OrderedDict()
    current_version = None

    # Iterate from oldest → newest (important for releases)
    commits = list(repo.iter_commits("HEAD"))
    commits.reverse()

    for commit in commits:
        lines = commit.message.strip().splitlines()
        if not lines:
            continue

        subject = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        if subject.lower().startswith("version"):
            current_version = subject
            releases[current_version] = []

            if body:
                releases[current_version].append(body)

        elif current_version and body:
            releases[current_version].append(body)

    return releases


def write_release_notes(notes):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Release Notes\n\n")

        for version, entries in notes.items():
            f.write(f"## {version}\n")
            for entry in entries:
                # Support multi-line commit bodies
                for line in entry.splitlines():
                    if line.strip():
                        f.write(f"- {line}\n")
            f.write("\n")

    print(f"✅ Release notes written to {OUTPUT_FILE}")


if __name__ == "__main__":
    repo = clone_or_open_repo()
    notes = extract_release_notes(repo)
    write_release_notes(notes)