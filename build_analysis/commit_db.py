import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List

@dataclass
class Commit:
    sha: str
    committed_date: int

    @staticmethod
    def from_dict(d: dict) -> 'Commit':
        return Commit(**d)


@dataclass
class CommitDb:
    HEAD: Commit
    num_commits: int
    file_commits: Dict[str, List[Commit]]

    @staticmethod
    def from_dict(d: dict) -> 'CommitDb':
        head = Commit.from_dict(d['HEAD'])
        num_commits = d['num_commits']
        file_commits = {
            f: [Commit.from_dict(c) for c in commits]
            for f, commits in d['file_commits'].items()
        }
        return CommitDb(
            HEAD=head,
            num_commits=num_commits,
            file_commits=file_commits,
        )

    @staticmethod
    def load(f) -> 'CommitDb':
        return CommitDb.from_dict(json.load(f))

    def save(self, f, indent: int = 2) -> None:
        json.dump(asdict(self), f, indent=indent)

def determine_update_frequencies(project_dir: str, files: List[str],
                                 commit_db: CommitDb) -> Dict[str, float]:
    update_frequency = {}

    latest_commit_date = commit_db.HEAD.committed_date
    file_commits = commit_db.file_commits
    project_path = Path(project_dir)

    for filename in files:
        commits = file_commits.get(filename, None)
        if commits is None:
            print(f"Warning: No commit info for {filename}")
            continue
        commit_dates = [c.committed_date for c in commits]
        num_updates = len(commit_dates)
        if num_updates == 0:
            print(f"Warning: Input {filename} not tracked by git", file=sys.stdout)
            continue

        # Ignore commits that were merged within a minute of each other
        # which might be a stack of PRs that were merged together
        commit_dates.append(latest_commit_date)
        commit_dates.sort()

        commits = [commit_dates[0]]
        for t in commit_dates[1:]:
            if t - commits[-1] > 60:
                commits.append(t)

        num_commits = len(commit_dates)

        days_since_creation = (latest_commit_date - commit_dates[0]) / (24 * 3600)
        update_frequency[filename] = days_since_creation / num_commits

    return update_frequency
