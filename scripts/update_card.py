import os
import subprocess
import requests
import json
from collections import defaultdict
import matplotlib.pyplot as plt

GITHUB_USERNAME = "KaliszSatInfo"
ORGS = ["SchoolStuffProjects"]
TOKEN = os.environ.get("GH_TOKEN")

HEADERS = {
    "Authorization": f"token {TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

TEMP_DIR = "temp_repos"
BAR_IMAGE_PATH = "language_usage_bar.svg"


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
    exclude_dirs = [
        "node_modules", "dist", "build", "out", ".next", ".output", "target", "vendor",
        "__pycache__", "storage", "var", "generated", "bin", "obj", "cache", ".venv",
        ".mypy_cache", ".pytest_cache", ".gradle", ".idea", ".dart_tool", "gen",
        "Packages", "Pods", "Carthage", ".parcel-cache"
    ]
    exclude_dir_str = ",".join(exclude_dirs)

    not_match_f = (
        r".*\.min\..*|"
        r".*\.map$|"
        r".*\.d\.ts$|"
        r".*\.pyc$|"
        r".*\.pyo$|"
        r".*\.egg-info$|"
        r".*\.class$|"
        r".*\.dll$|"
        r".*\.exe$|"
        r".*\.jar$|"
        r".*\.war$|"
        r".*\.ear$|"
        r".*\.so$|"
        r".*\.a$|"
        r".*\.o$|"
        r".*\.hi$|"
        r".*\.bc$|"
        r".*\.tsbuildinfo$"
    )

    result = subprocess.run([
        "cloc", path,
        "--json",
        f"--exclude-dir={exclude_dir_str}",
        f"--not-match-f={not_match_f}"
    ], capture_output=True, text=True)

    try:
        cloc_data = json.loads(result.stdout)
        return cloc_data
    except json.JSONDecodeError:
        return {}

def aggregate_language_data(repos):
    repo_language_data = {}

    excluded_repos = {"mediawiki"}

    for repo in repos:
        if repo["name"] in excluded_repos:
            print(f"Skipping: {repo['name']}")
            continue

        print(f"Processing: {repo['name']}")
        path = clone_repo(repo["clone_url"], repo["name"])
        cloc_data = run_cloc(path)

        language_lines = {
            lang: stats["code"]
            for lang, stats in cloc_data.items()
            if lang not in ["header", "SUM"]
        }

        repo_language_data[repo["name"]] = language_lines

    return repo_language_data


def compute_language_stats(repo_language_data):
    lang_repo_count = defaultdict(int)
    lang_loc_sum = defaultdict(int)

    for repo, langs in repo_language_data.items():
        for lang, loc in langs.items():
            if loc > 0:
                lang_repo_count[lang] += 1
                lang_loc_sum[lang] += loc

    return lang_repo_count, lang_loc_sum

def apply_penalty_formula(repo_language_data):
    penalty_heavy = 0.02
    penalty_generated = 0.1
    penalty_neutral = 1.0

    heavily_penalized = {
        "YAML", "Markdown", "SVG", "XML", "INI", "Text",
        "Lua", "HLSL", "XSD", "PowerShell", "DOS Batch",
        "C/C++ Header", "Visual Studio Solution", "CSV", "Ant"
    }

    generated_or_config = {
        "JSON", "LESS", "SCSS", "Unity-Prefab", "peg.js", "Windows Module Definition", "AsciiDoc",
        "CoffeeScript", "reStructuredText", "Properties", "TOML", "Maven", "PEG", "FXML",
        "vim script", "diff", "Handlebars", "CSS", "ASP.NET"
    }

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
        if percent > 0.5 or lang in {"Python", "TypeScript", "Java"}:
            normalized[lang] = percent
    return dict(sorted(normalized.items(), key=lambda x: x[1], reverse=True))

def generate_language_bar_image(normalized_scores):
    labels = list(normalized_scores.keys())
    sizes = list(normalized_scores.values())
    colors_map = {
        "PHP": "#4caf50",
        "JavaScript": "#2196f3",
        "JSON": "#ff9800",
        "CSS": "#9c27b0",
        "HTML": "#f44336",
        "Java": "#00bcd4",
        "TypeScript": "#ff5722",
        "Python": "#607d8b"
    }
    colors = [colors_map.get(lang, "#888888") for lang in labels]

    fig, ax = plt.subplots(figsize=(8, 1.5))
    left = 0
    for i, (label, size) in enumerate(zip(labels, sizes)):
        ax.barh(0, size, left=left, color=colors[i])
        if size > 3:
            ax.text(left + size / 2, 0, f"{label} {size:.1f}%", va='center', ha='center', color='white', fontsize=10)
        left += size

    ax.set_xlim(0, 100)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(BAR_IMAGE_PATH, transparent=True, format='svg')
    plt.close()

def generate_markdown_with_image_and_table(normalized_scores, repo_counts, loc_sums):
    lines = [
        "### Language Usage\n",
        f"![Language Usage]({BAR_IMAGE_PATH})\n",
        "| Language | Percentage | Repos | LOC |",
        "| --- | ---: | ---: | ---: |"
    ]
    for lang, percent in normalized_scores.items():
        repos = repo_counts.get(lang, 0)
        loc = loc_sums.get(lang, 0)
        lines.append(f"| {lang} | {percent}% | {repos} | {loc} |")
    return "\n".join(lines)

def update_readme(content):
    start_marker = "<!-- START_SECTION:language-usage -->"
    end_marker = "<!-- END_SECTION:language-usage -->"

    with open("README.md", "r", encoding="utf-8") as f:
        readme = f.read()

    before = readme.split(start_marker)[0]
    after = readme.split(end_marker)[1]

    new_readme = before + start_marker + "\n" + content + "\n" + end_marker + after

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_readme)

def main():
    reset_temp_dir()
    repos = fetch_repos(GITHUB_USERNAME) + sum([fetch_repos(org, is_org=True) for org in ORGS], [])
    repo_language_data = aggregate_language_data(repos)
    normalized_scores = apply_penalty_formula(repo_language_data)
    repo_counts, loc_sums = compute_language_stats(repo_language_data)

    for lang in ["JSON", "ASP.NET", "Unity-Prefab"]:
        normalized_scores.pop(lang, None)
        repo_counts.pop(lang, None)
        loc_sums.pop(lang, None)

    generate_language_bar_image(normalized_scores)

    markdown_content = generate_markdown_with_image_and_table(normalized_scores, repo_counts, loc_sums)
    update_readme(markdown_content)

if __name__ == "__main__":
    main()
