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
    repo_count = defaultdict(int)

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
            repo_count[lang] += 1

    return language_lines, repo_count

def compute_weighted_usage(language_lines, repo_count):
    total_lines = sum(language_lines.values())
    total_repos = sum(repo_count.values())
    weighted = {}

    for lang in language_lines:
        loc_share = language_lines[lang] / total_lines if total_lines else 0
        repo_share = repo_count[lang] / total_repos if total_repos else 0
        weight = 0.7 * repo_share + 0.3 * loc_share
        weighted[lang] = weight

    return dict(sorted(weighted.items(), key=lambda x: x[1], reverse=True))

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
    language_lines, repo_count = aggregate_language_data(repos)
    weighted = compute_weighted_usage(language_lines, repo_count)

    bar = ""
    total = sum(weighted.values())
    for lang, score in weighted.items():
        percent = round(score / total * 100, 1) if total else 0
        bar += f"{lang} [{percent}%] " + "█" * int(percent / 5) + "\n"

    markdown_content = "### 📊 **Weighted Language Usage**\n\n```\n" + bar + "```\n"
    update_readme(markdown_content)

if __name__ == "__main__":
    main()
