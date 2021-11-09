import git  # type: ignore
from collections import defaultdict
from .commit_db import CommitDb, Commit
from typing import Dict, Set, List

try:
    from tqdm import tqdm  # type: ignore
except ImportError:
    def tqdm(iterable, total):
        return iterable

def append_files(files: Set[str], tree):
    for item in tree.traverse():
        if isinstance(item, git.Tree):
            append_files(files, item)
        elif isinstance(item, git.Blob):
            files.add(item.path)

def build_commit_db(repo_path: str, main_branch: str) -> CommitDb:
    repo = git.Repo(str(repo_path))
    master = repo.rev_parse(main_branch)

    current_files: Set[str] = set()
    append_files(current_files, master.tree)

    renamed_files: Dict[str, str] = {}
    def handle_renamed(filename):
        head = filename.find('{')
        tail = filename.rfind('}')
        split = filename.find(' => ', head)
        from_fn = filename[:head] + filename[head + 1:split] + filename[tail + 1:]
        to_fn = filename[:head] + filename[split + 4:tail] + filename[tail + 1:]

        to_fn = renamed_files.get(to_fn, to_fn)
        renamed_files[from_fn] = to_fn
        return (from_fn, to_fn)

    num_commits = master.count()
    file_commits: Dict[str, List[Commit]] = {}

    for commit in tqdm(repo.iter_commits(master.hexsha), total=num_commits):
        effected_files = commit.stats.files.keys()
        commit_log = Commit(sha=commit.hexsha, committed_date=commit.committed_date)
        for fn in effected_files:
            if "=>" in fn:
                from_fn, to_fn = handle_renamed(fn)
                fn = to_fn
            else:
                fn = renamed_files.get(fn, fn)

            if fn not in current_files:
                continue

            if fn in file_commits:
                file_commits[fn].append(commit_log)
            else:
                file_commits[fn] = [commit_log]

    return CommitDb(
        HEAD=Commit(sha=master.hexsha, committed_date=master.committed_date),
        num_commits=num_commits,
        file_commits=file_commits,
    )
