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
PIE_IMAGE_PATH = "language_usage_pie.png"

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

def aggregate_language_data(repos, min_loc_threshold=50):
    repo_language_data = {}
    EXCEPTIONS = {"Python", "TypeScript"}

    for repo in repos:
        name = repo["name"]
        url = repo["clone_url"]
        print(f"Processing: {name}")
        path = clone_repo(url, name)
        cloc_data = run_cloc(path)

        language_lines = {}
        for lang, stats in cloc_data.items():
            if lang in ["header", "SUM", "JSON"]:
                continue
            if stats["code"] < min_loc_threshold and lang not in EXCEPTIONS:
                continue
            language_lines[lang] = stats["code"]
        repo_language_data[name] = language_lines

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
        "vim script", "diff", "Handlebars"
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


COLOR_MAP = {
    "PHP": "#6e4fab",
    "JavaScript": "#f7df1e",
    "HTML": "#e34f26",
    "CSS": "#1572b6",
    "Python": "#3572A5",
    "Java": "#b07219",
    "TypeScript": "#3178c6",
}


def generate_language_pie_chart(normalized_scores, output_path=PIE_IMAGE_PATH):
    labels = list(normalized_scores.keys())
    sizes = list(normalized_scores.values())
    colors = [COLOR_MAP.get(lang, "#888888") for lang in labels]

    plt.figure(figsize=(6, 6))
    plt.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct='%1.1f%%',
        startangle=140,
        textprops={'fontsize': 10}
    )
    plt.axis('equal')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def generate_html_with_image_and_table(normalized_scores, repo_counts, loc_sums, pie_chart_path=PIE_IMAGE_PATH):
    rows = []
    for lang, percent in normalized_scores.items():
        repos = repo_counts.get(lang, 0)
        loc = loc_sums.get(lang, 0)
        rows.append(f"""
        <tr>
            <td>{lang}</td>
            <td style="text-align:right;">{percent}%</td>
            <td style="text-align:right;">{repos}</td>
            <td style="text-align:right;">{loc}</td>
        </tr>
        """)

    table_html = f"""
    <table>
      <thead>
        <tr>
          <th>Language</th>
          <th style="text-align:right;">Adjusted %</th>
          <th style="text-align:right;">Repos Using</th>
          <th style="text-align:right;">Total LOC</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
    """

    combined_html = f"""
<div style="display: flex; align-items: flex-start; gap: 20px; flex-wrap: wrap;">
  <div style="flex: 1; min-width: 320px; overflow-x: auto;">
    {table_html}
  </div>

  <div style="flex: 1; min-width: 320px;">
    <img src="{pie_chart_path}" alt="Language Usage Pie Chart" style="max-width: 100%; height: auto; border-radius: 8px;" />
  </div>
</div>
"""
    return "### Language Usage\n\n" + combined_html

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

    generate_language_pie_chart(normalized_scores)

    markdown_content = generate_html_with_image_and_table(normalized_scores, repo_counts, loc_sums)
    update_readme(markdown_content)


if __name__ == "__main__":
    main()
