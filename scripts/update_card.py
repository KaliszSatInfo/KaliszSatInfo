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

EXCLUDE_DIRS = ["node_modules", "vendor", ".git", "dist", "build", "out"]

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
    subprocess.run(["git", "clone", "--depth", "1", git_url, target_path],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target_path

def run_cloc(path):
    exclude_dirs_str = ",".join(EXCLUDE_DIRS)
    result = subprocess.run(
        ["cloc", path, f"--exclude-dir={exclude_dirs_str}", "--json"],
        capture_output=True, text=True)
    try:
        cloc_data = json.loads(result.stdout)
        return cloc_data
    except json.JSONDecodeError:
        return {}

def aggregate_language_data(repos):
    repo_language_data = {}

    for repo in repos:
        name = repo["name"]
        url = repo["clone_url"]
        print(f"Processing: {name}")
        path = clone_repo(url, name)
        cloc_data = run_cloc(path)

        language_lines = {}
        for lang, stats in cloc_data.items():
            if lang in ["header", "SUM"]:
                continue
            language_lines[lang] = stats["code"]
        repo_language_data[name] = language_lines

    return repo_language_data

def apply_penalty_formula(repo_language_data):
    penalty_heavy = 0.02
    penalty_generated = 0.1
    penalty_neutral = 1.0
    penalty_boost = 1.0
    heavily_penalized = {
        "YAML", "Markdown", "SVG", "XML", "INI", "Text", 
        "Lua", "HLSL", "XSD", "PowerShell", "DOS Batch",
        "C/C++ Header", "Arduino Sketch", "Visual Studio Solution", "CSV", "Ant"
    }
    
    generated_or_config = {
        "JSON", "LESS", "SCSS", "Unity-Prefab", "peg.js", "Windows Module Definition", "AsciiDoc",
        "CoffeeScript", "reStructuredText", "Properties", "TOML", "Maven", "PEG", "FXML",
        "vim script", "diff", "Handlebars"
    }
    
    boosted_langs = set()
    
    adjusted_scores = defaultdict(float)
    
    repo_sizes = {repo: sum(langs.values()) for repo, langs in repo_language_data.items()}
    max_repo_size = max(repo_sizes.values()) if repo_sizes else 1
    
    for repo, langs in repo_language_data.items():
        repo_size = repo_sizes[repo]
        size_penalty = 1 / (1 + (repo_size / max_repo_size) ** 2.5)
        
        for lang, loc in langs.items():
            if lang in heavily_penalized:
                factor = penalty_heavy
            elif lang in generated_or_config:
                factor = penalty_generated
            else:
                factor = penalty_neutral
            
            adjusted_score = loc * factor * size_penalty
                        
            adjusted_scores[lang] += adjusted_score
    
    total = sum(adjusted_scores.values())
    normalized = {}
    for lang, score in adjusted_scores.items():
        percent = round(score / total * 100, 2)
        if percent > 0.5 or lang in {"Python", "TypeScript"}:
            normalized[lang] = percent
    return dict(sorted(normalized.items(), key=lambda x: x[1], reverse=True))

def generate_markdown_adjusted(normalized_scores):
    lines = ["### 📊 Language Usage (Adjusted with Penalties)\n"]
    lines.append("| Language | Adjusted % |")
    lines.append("| --- | ---: |")
    for lang, percent in normalized_scores.items():
        lines.append(f"| {lang} | {percent}% |")
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
    repo_language_data = aggregate_language_data(repos)
    normalized_scores = apply_penalty_formula(repo_language_data)
    markdown_content = generate_markdown_adjusted(normalized_scores)
    update_readme(markdown_content)

if __name__ == "__main__":
    main()
