#!/usr/bin/env python3
"""
Script to order projects under "Tools & Other Projects founded by DaoCloud or DaoClouder"
Requirements:
1. matrixhub on top of the list
2. other projects order by stars
3. move project to the last line with name only if the repo is not updated for more than 3 months
"""

import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import time

def extract_github_repo(line: str) -> Tuple[str, str, str]:
    """
    Extract GitHub repository info from markdown line.
    Returns (org/repo, description, full_line)
    """
    # Pattern: - [name](url): description
    match = re.match(r'- \[([^\]]+)\]\(https://github.com/([^)]+)\):?\s*(.*)', line)
    if match:
        name = match.group(1)
        repo = match.group(2)
        description = match.group(3)
        return repo, description, line
    return None, None, line

def get_repo_info(repo: str, token: str = None) -> Dict:
    """
    Fetch repository information from GitHub API
    Returns dict with stars and last_updated
    """
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    
    try:
        url = f'https://api.github.com/repos/{repo}'
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'stars': data.get('stargazers_count', 0),
                'last_updated': data.get('updated_at', ''),
                'name': data.get('name', ''),
                'full_name': data.get('full_name', repo)
            }
        else:
            print(f"Warning: Failed to fetch {repo}: {response.status_code}")
            return {'stars': 0, 'last_updated': '', 'name': repo, 'full_name': repo}
    except Exception as e:
        print(f"Error fetching {repo}: {e}")
        return {'stars': 0, 'last_updated': '', 'name': repo, 'full_name': repo}

def is_stale(last_updated: str, months: int = 3) -> bool:
    """
    Check if repository hasn't been updated in the last N months
    """
    if not last_updated:
        return False
    
    try:
        last_update_date = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
        threshold = datetime.now(last_update_date.tzinfo) - timedelta(days=months * 30)
        return last_update_date < threshold
    except Exception as e:
        print(f"Error parsing date {last_updated}: {e}")
        return False

def order_projects(readme_path: str, token: str = None):
    """
    Read README, order the Tools & Other Projects section, and write back
    """
    with open(readme_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the "Tools & Other Projects" section
    section_start = -1
    section_end = -1
    
    for i, line in enumerate(lines):
        if 'Tools & Other Projects founded by DaoCloud or DaoClouder' in line:
            section_start = i + 1
            # Find the end of this section (next ### or end of file)
            for j in range(i + 1, len(lines)):
                if lines[j].startswith('###') or lines[j].startswith('##'):
                    section_end = j
                    break
            if section_end == -1:
                section_end = len(lines)
            break
    
    if section_start == -1:
        print(f"Could not find 'Tools & Other Projects' section in {readme_path}")
        return
    
    print(f"Found section from line {section_start} to {section_end}")
    
    # Extract all project lines
    projects = []
    non_project_lines = []
    
    for i in range(section_start, section_end):
        line = lines[i]
        if line.strip().startswith('- [') and 'github.com' in line:
            repo, description, full_line = extract_github_repo(line.strip())
            if repo:
                projects.append({
                    'line': full_line,
                    'repo': repo,
                    'description': description,
                    'original_index': i
                })
        else:
            non_project_lines.append((i, line))
    
    print(f"Found {len(projects)} projects")
    
    # Fetch repo info for each project
    for project in projects:
        print(f"Fetching info for {project['repo']}...")
        info = get_repo_info(project['repo'], token)
        project.update(info)
        time.sleep(0.5)  # Rate limiting
    
    # Separate matrixhub, active projects, and stale projects
    matrixhub = None
    active_projects = []
    stale_projects = []
    
    for project in projects:
        if 'matrixhub' in project['repo'].lower():
            matrixhub = project
        elif is_stale(project['last_updated']):
            stale_projects.append(project)
        else:
            active_projects.append(project)
    
    # Sort active projects by stars (descending)
    active_projects.sort(key=lambda x: x['stars'], reverse=True)
    
    # Build new section
    new_section = []
    
    # Add matrixhub first
    if matrixhub:
        new_section.append(matrixhub['line'] + '\n')
    
    # Add active projects sorted by stars
    for project in active_projects:
        new_section.append(project['line'] + '\n')
    
    # Add stale projects (name only)
    for project in stale_projects:
        # Extract just the name part
        match = re.match(r'- \[([^\]]+)\]', project['line'])
        if match:
            name = match.group(1)
            new_section.append(f'- {name}\n')
        else:
            new_section.append(project['line'] + '\n')
    
    # Reconstruct the file
    new_lines = lines[:section_start] + new_section + lines[section_end:]
    
    # Write back
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Updated {readme_path}")
    print(f"  - matrixhub: {'Found' if matrixhub else 'Not found'}")
    print(f"  - Active projects: {len(active_projects)}")
    print(f"  - Stale projects: {len(stale_projects)}")

if __name__ == '__main__':
    import os
    
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("Warning: GITHUB_TOKEN not set. API rate limits will be lower.")
    
    readme_en = '/home/runner/work/.github/.github/profile/README.md'
    readme_zh = '/home/runner/work/.github/.github/profile/README_zh.md'
    
    print("Processing English README...")
    order_projects(readme_en, token)
    
    print("\nProcessing Chinese README...")
    order_projects(readme_zh, token)
    
    print("\nDone!")
