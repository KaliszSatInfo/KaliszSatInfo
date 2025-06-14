import os
import subprocess
import requests
import json
from collections import defaultdict

GITHUB_USERNAME = "KaliszSatInfo"
ORGS = ["SchoolStuffProjects"]
TOKEN = os.environ.get("GH_TOKEN")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

TEMP_DIR = "temp_repos"

def reset_temp_dir():
    if os.path.exists(TEMP_DIR):
        subprocess.run(["rm", "-rf", TEMP_DIR])
    os.makedirs(TEMP_DIR, exist_ok=True)

def fetch_repos(user_or_org, is_org=False):
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/{'orgs' if is_org else 'users'}/{user_or_org}/repos?per_page=100&page={page}"
        response = requests.get(url, headers=HEADERS)
        data = response.json()
        if not data or 'message' in data:
            break
        repos.extend(data)
        if len(data) < 100:
            break
        page += 1
    return repos

def clone_repo(git_url, name):
    target_path = os.path.join(TEMP_DIR, name)
    subprocess.run(["git", "clone", "--depth", "1", git_url, target_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target_path

def run_cloc(path):
    result = subprocess.run(["cloc", path, "--json"], capture_output=True, text=True)
    try:
        cloc_data = json.loads(result.stdout)
        return cloc_data
    except json.JSONDecodeError:
        return {}

def aggregate_language_data(repos):
    language_lines = defaultdict(int)

    for repo in repos:
        name = repo["name"]
        url = repo["clone_url"]
        print(f"Processing: {name}")
        path = clone_repo(url, name)
        cloc_data = run_cloc(path)
        for lang, stats in cloc_data.items():
            if lang in ["header", "SUM"]:
                continue
            language_lines[lang] += stats["code"]

    return language_lines

def generate_markdown_raw(language_lines):
    sorted_langs = sorted(language_lines.items(), key=lambda x: x[1], reverse=True)
    lines = ["### 📊 Language Usage (Raw Lines of Code)\n"]
    lines.append("| Language | Lines of Code |")
    lines.append("| --- | ---: |")
    for lang, loc in sorted_langs:
        lines.append(f"| {lang} | {loc} |")
    return "\n".join(lines)

def update_readme(content):
    start_marker = "<!-- START_SECTION:language-usage -->"
    end_marker = "<!-- END_SECTION:language-usage -->"

    with open("README.md", "r") as f:
        readme = f.read()

    before = readme.split(start_marker)[0]
    after = readme.split(end_marker)[1]

    new_readme = before + start_marker + "\n" + content + "\n" + end_marker + after

    with open("README.md", "w") as f:
        f.write(new_readme)

def main():
    reset_temp_dir()
    repos = fetch_repos(GITHUB_USERNAME) + sum([fetch_repos(org, is_org=True) for org in ORGS], [])
    language_lines = aggregate_language_data(repos)
    markdown_content = generate_markdown_raw(language_lines)
    update_readme(markdown_content)

if __name__ == "__main__":
    main()
